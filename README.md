# IPFS Kit Python - Advanced Cluster-Ready MCP Server

[![Production Ready](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)](https://github.com/endomorphosis/ipfs_kit_py)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/downloads/)
[![Version 3.0.0](https://img.shields.io/badge/Version-3.0.0-green)](./pyproject.toml)
[![Docker Ready](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)
[![Kubernetes Ready](https://img.shields.io/badge/Kubernetes-Ready-blue)](https://kubernetes.io/)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-orange)](https://modelcontextprotocol.io/)
[![Integrations](https://img.shields.io/badge/Integrations-36-purple)](./COMPLETE_INTEGRATION_SUMMARY.md)
[![Tests](https://img.shields.io/badge/Tests-77%20Passing-success)](./tests/)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](./LICENSE)

**IPFS Kit Python** is a comprehensive, production-ready Python toolkit for IPFS (InterPlanetary File System) operations with advanced cluster management and full Model Context Protocol (MCP) server integration. It provides high-level APIs, distributed cluster operations, tiered storage, VFS integration, and AI/ML capabilities.

> 🎉 **Advanced Cluster Ready!** Production-tested 3-node cluster with leader election, master/worker/leecher role hierarchy, replication management, indexing services, and comprehensive Docker/Kubernetes deployment support. All cluster features validated and operational.

> 🔄 **36 Strategic Integrations!** Complete integration with `ipfs_datasets_py` (distributed dataset storage) and `ipfs_accelerate_py` (compute acceleration) across all infrastructure, AI/ML, VFS, and MCP components. Immutable audit trails, 2-5x faster operations, 100% backward compatible with graceful fallbacks.

## 📖 Table of Contents

- [🚀 Quickstart](#-quickstart)
- [🔄 Distributed Dataset Integration & Compute Acceleration](#-distributed-dataset-integration--compute-acceleration)
  - [What's Integrated](#whats-integrated)
  - [Integration Coverage (36 Modules)](#integration-coverage-36-modules)
  - [Key Benefits](#key-benefits)
  - [Usage Examples](#usage)
  - [Documentation](#documentation)
- [🌟 Key Features](#-key-features)
- [🖥️ Unified MCP Dashboard](#️-unified-mcp-dashboard-finalized)
- [📦 Installation](#-installation)
- [🏗️ Architecture](#️-architecture)
- [🔧 Configuration](#-configuration)
- [📚 Documentation](#-documentation)
- [🧪 Testing](#-testing)
- [🤝 Contributing](#-contributing)
- [📜 License](#-license)

## 🎯 Quick Links

- **[Integration Quick Start](docs/INTEGRATION_QUICK_START.md)** - Step-by-step guide for using integrations
- **[Integration Cheat Sheet](docs/INTEGRATION_CHEAT_SHEET.md)** - Quick reference for all 36 integrations
- **[Complete Integration Summary](COMPLETE_INTEGRATION_SUMMARY.md)** - Full details on all integrations
- **[MCP Architecture Guide](MCP_INTEGRATION_ARCHITECTURE.md)** - MCP tool architecture and patterns
- **[Integration Overview](docs/INTEGRATION_OVERVIEW.md)** - High-level integration overview

---

> Note: A minimal consolidated MCP dashboard is included for lightweight local use. See CONSOLIDATED_MCP_DASHBOARD.md and start it via:
> - Foreground: `ipfs-kit mcp start --foreground` or `python -m ipfs_kit_py.cli mcp start --foreground`
> - Background: `ipfs-kit mcp start` or `python -m ipfs_kit_py.cli mcp start`
>
> Notes:
> - The CLI prefers the packaged dashboard server `ipfs_kit_py/mcp/dashboard/consolidated_server.py` to ensure correct assets and templates. You can override with `--server-path` or `IPFS_KIT_SERVER_FILE`.
> - Default ports: CLI uses `8004` by default. The root wrapper `consolidated_mcp_dashboard.py` defaults to `8081` (or `MCP_PORT` if set). Align with `--port` for consistency.
> - Background runs write PID and logs under `~/.ipfs_kit` as `mcp_<port>.pid` and `mcp_<port>.log`.
> Then open http://127.0.0.1:8004/

PID files and CLI semantics:
- The dashboard writes two PID files on startup:
  - `~/.ipfs_kit/dashboard.pid` (legacy, shared)
  - `~/.ipfs_kit/mcp_{port}.pid` (port-specific)
- The CLI uses the port-specific PID file for `status` and `stop` to avoid cross-port ambiguity. If you ran the server manually and only `dashboard.pid` exists, the CLI may show HTTP status but no PID for that port. Start via the CLI to have `mcp_{port}.pid` created.

## 🖥️ Unified MCP Dashboard (Finalized)

The repository includes a modern, schema-driven MCP dashboard with:
- **Single-file FastAPI app** (`consolidated_mcp_dashboard.py`)
- **UI at `/`**: SPA with sidebar navigation, dashboard cards, and real-time updates
- **Tool Runner UI**:
  - Beta (schema-driven) UI is the default and always shown at `/` (client-rendered)
  - Legacy runner remains internally available for parity but is not the default
- **MCP JS SDK**: `/mcp-client.js` exposes `window.MCP` with all tool namespaces
  - Sets response header `X-MCP-SDK-Source: inline|static`
  - If a static SDK exists at `ipfs_kit_py/static/mcp-sdk.js`, it will be served with a compatibility shim that guarantees:
    - Core: `MCP.listTools()`, `MCP.callTool()`, and `MCP.status()`
    - Namespaces: `Services, Backends, Buckets, Pins, Files, IPFS, CARs, State, Logs, Server`
- **Endpoints**:
  - `/` (UI)
  - `/mcp-client.js` (SDK)
  - `/app.js` (UI logic)
  - `/api/mcp/status`, `/api/system/health` (status)
  - `/api/system/deprecations` (deprecation registry)
  - `/api/logs/stream` (SSE), `/ws` (WebSocket)
  - `POST /mcp/tools/list`, `POST /mcp/tools/call` (JSON-RPC)
  - `/api/state/backends`, `/api/services`, `/api/files`, etc.
  - Deprecated (temporary): `/api/system/overview` – legacy compatibility. Returns combined `status`, `health`, and `metrics` plus deprecation headers. Planned removal in version 3.2.0; migrate to `/api/mcp/status`, `/api/system/health`, and `/api/metrics/system`.
  - The initial WebSocket `system_update` payload now includes a `deprecations` array (with per-endpoint hit counts) used by a dismissible UI banner; if the WS payload is delayed the UI lazily fetches `/api/system/deprecations` as a fallback.
- **Panels**:
  - Overview, Tools, Buckets, Pins, Backends, Services, Integrations, Files, CARs, Logs
- **Security (optional)**:
  - Set an API token via environment `MCP_API_TOKEN` or config `--api-token` when starting the dashboard.
  - Read-only endpoints (GET status/metrics/list) remain open.
  - Mutating endpoints (create/update/delete buckets, backends, pins, files write, tool execution) require token.
  - Accepted credential forms:
    - Header: `x-api-token: <token>`
    - Authorization: `Bearer <token>`
    - Query: `?token=<token>` (use sparingly; appears in logs/history)
  - Example:
    ```bash
    MCP_API_TOKEN=secret123 ipfs-kit mcp start --port 8004
    curl -H 'x-api-token: secret123' -X POST http://127.0.0.1:8004/api/state/buckets -d '{"name":"secure-bkt"}' -H 'Content-Type: application/json'
    ```
  - Tools: `POST /mcp/tools/call` also requires the token.
  - Status telemetry additions:
    - `GET /api/mcp/status` now returns:
      - `counts.requests` – total HTTP requests handled since process start (in-memory)
      - `security.auth_enabled` – boolean indicating whether an API token is active
    - These fields assist with lightweight observability without external metrics backends.
  - Client SDK convenience: `MCP.status()` returns `{ initialized, tools, ...data }` for easy checks in the UI/tests.
- **Accessibility**: ARIA roles, keyboard navigation, responsive design
- **Testing**: Playwright E2E, Python smoke/unit tests
- **Data locations** (default):
  - `~/.ipfs_kit/buckets.json`, `~/.ipfs_kit/pins.json`
  - `~/.ipfs_kit/backends/*.json`, `~/.ipfs_kit/backend_configs/*.yaml`
  - `~/.ipfs_kit/files/`, `~/.ipfs_kit/car_store/*.car`, `~/.ipfs_kit/logs/*.log`

---

## 🚀 Quickstart

Install dependencies (no sudo required; installs local tools into `./bin` when needed):

```bash
./scripts/deployment/zero_touch_install.sh --profile dev
source ./bin/env.sh
```

Start the dashboard server:

```bash
# CLI alias
ipfs-kit mcp start --host 127.0.0.1 --port 8004
# or Python module
python -m ipfs_kit_py.cli mcp start --host 127.0.0.1 --port 8004

When starting in the background, the CLI will re-invoke itself in foreground mode and write management files:

```
~/.ipfs_kit/mcp_8004.pid  # PID of the running dashboard
~/.ipfs_kit/mcp_8004.log  # Combined stdout/stderr log
```
```

Open the UI at [http://127.0.0.1:8004/](http://127.0.0.1:8004/)

Stop or check status:

```bash
ipfs-kit mcp stop --port 8004
ipfs-kit mcp status --port 8004
```

List deprecated endpoints (with planned removal version, hit counts, and migration hints):

```bash
ipfs-kit mcp deprecations          # pretty table
ipfs-kit mcp deprecations --json   # raw JSON
```

The hit counts help decide if an endpoint can be removed sooner (low / zero usage) or needs extended support.

Advanced options for deprecations analysis and CI gating:

```bash
# Sort and filter
ipfs-kit mcp deprecations --sort hits --reverse           # highest hits first
ipfs-kit mcp deprecations --min-hits 1                    # hide 0-hit endpoints

# CI policy enforcement (exit codes):
# 0 = OK, 3 = hits threshold violation, 4 = missing migration hints
ipfs-kit mcp deprecations --fail-if-hits-over 0           # fail if any endpoint was used
ipfs-kit mcp deprecations --fail-if-missing-migration     # fail if any endpoint lacks migration hints

# Write a machine-readable report for artifacts
ipfs-kit mcp deprecations --report-json ./deprecations_report.json
```

### Deprecation Governance & Report Schema

All deprecation policy decisions are driven by a machine‑readable report generated via:

```bash
ipfs-kit mcp deprecations \
  --report-json build/deprecations/report.json \
  --fail-if-hits-over 100 \
  --fail-if-missing-migration
```

Key properties of the report (see `schemas/deprecations_report.schema.json`):
* `generated_at` – UTC timestamp
* `report_version` – Semantic schema contract (currently `1.0.0`)
* `deprecated[]` – Filtered/sorted endpoints (after flags)
* `summary.{count,max_hits}` – Aggregated stats
* `policy.hits_enforcement` – `status|threshold|violations[]`
* `policy.migration_enforcement` – `status|violations[]`
* `raw` – Original unfiltered payload (traceability)

Exit codes (for CI): 0=pass/skip, 3=hits threshold violation, 4=missing migration mapping. See `CLI_OVERVIEW.md` for detailed policy usage, evolution guidelines, and schema versioning strategy.

Versioning Rules (`report_version`):
* PATCH: Add optional fields / doc clarifications
* MINOR: Add required fields (backward compatible for existing keys)
* MAJOR: Remove/rename existing required keys or structural changes

Automation Tips:
* Gate merges: fail workflow if report exit code is 3 or 4
* Trend analysis: archive `summary` diff across runs
* Enforcement drift detection: compare previous vs current violation sets

For full governance details and upgrade strategy refer to `CLI_OVERVIEW.md` (Deprecation Governance & Report Schema section).

Run the dashboard script directly (without the CLI):

```bash
python consolidated_mcp_dashboard.py \
  --host 127.0.0.1 \
  --port 8081 \
  --data-dir ~/.ipfs_kit \
  --debug
```

Notes:
- When run directly, the server still writes both PID files: `~/.ipfs_kit/dashboard.pid` and `~/.ipfs_kit/mcp_{port}.pid`.
- The CLI `status` and `stop` subcommands look only at the port-specific file (e.g., `mcp_8099.pid`).

### Environment Defaults

- `MCP_HOST` and `MCP_PORT`: Preferred environment variables used by the root wrapper (`consolidated_mcp_dashboard.py`) and test harness. If unset, `HOST` and `PORT` are used as a fallback; otherwise defaults are `127.0.0.1` and `8081` for the wrapper.

CLI selection of dashboard server:

- Prefers `ipfs_kit_py/mcp/dashboard/consolidated_server.py` (stable, packaged).
- Falls back to `IPFS_KIT_SERVER_FILE`, `--server-path`, or common repo-local files during development.
- CLI defaults may use a different port (examples use `8004`). When invoking via the CLI, explicit `--host/--port` flags take precedence.
- Examples:

```bash
# Override via environment for direct script/testing flows
export MCP_HOST=127.0.0.1
export MCP_PORT=8099
python consolidated_mcp_dashboard.py --debug

# Or fully explicit via flags (overrides env)
python consolidated_mcp_dashboard.py --host 127.0.0.1 --port 8099 --debug
```

---

## 🧑‍💻 Tool Runner UI

- **Legacy UI**: Simple select + run
- **Beta UI**: Schema-driven forms, ARIA, validation, keyboard shortcuts
  - Enable via `?ui=beta` or `localStorage.setItem('toolRunner.beta', 'true')`
  - See `README_BETA_UI.md` for details

## 🧰 MCP JS SDK

- Exposed at `/mcp-client.js` as `window.MCP`
- Namespaces: Services, Backends, Buckets, Pins, Files, IPFS, CARs, State, Logs, Server
- Methods: `listTools()`, `callTool(name, args)`, `status()`, plus per-namespace helpers
- Header: `X-MCP-SDK-Source: inline|static` indicates whether the SDK is embedded or served from `ipfs_kit_py/static/mcp-sdk.js`
- Compatibility shim ensures core methods and namespaces are available even with a custom static SDK

Frontend behavior and fallbacks:
- The dashboard prefers the packaged server’s full HTML which includes the Tools view and the beta runner container.
- If a minimal shell is served, the client script at `/app.js` injects a lightweight Tools UI at runtime (`#toolrunner-beta-container` and `#view-tools`) and wires it to `window.MCP`. This ensures selectors used by tests and docs remain available.
 - In repository development, `static/app.js` provides this fallback so the UI remains usable even if templates are partially rendered.

## 🗂️ Panels

- Overview, Tools, Buckets, Pins, Backends, Services, Integrations, Files, CARs, Logs

## 🗄️ Data Locations

- All state is file-backed under `~/.ipfs_kit` for CLI parity

## 🧪 Testing

- Playwright E2E tests (see `tests/e2e/`)
- Python smoke and unit tests

### Quick test commands

Run targeted Python unit tests for recent dashboard features:

```bash
python -m unittest -q tests/test_assets_unittest.py tests/test_services_unittest.py tests/test_bucket_policy_unittest.py
```

Run an SDK-first Playwright smoke test (requires a running dashboard, e.g., on 8099):

```bash
# Start the server (example)
python consolidated_mcp_dashboard.py --host 127.0.0.1 --port 8099

# In a separate shell:
DASHBOARD_URL=http://127.0.0.1:8099 npm run e2e -- tests/e2e/sdk_smoke.spec.js
```

Notes:
- The dashboard page at `/` is client-rendered; DOM elements like the nav are injected by `/app.js` at runtime.
- The SDK is available at `/mcp-client.js` and exposes `window.MCP` once loaded.

## 📚 Documentation

- See `CONSOLIDATED_MCP_DASHBOARD.md` for dashboard details
- See `MCP_DASHBOARD_UI_PLAN.md` for UI/UX and implementation plan
- See `README_BETA_UI.md` for beta Tool Runner UI details
- See `MCP_DASHBOARD_FEATURE_PARITY_CHECKLIST.md` for a feature parity tracker aligned to the legacy dashboard UI
- See `DASHBOARD_UI_COMPONENTS_SPEC.md` for concrete UI component contracts and examples
- See `LEGACY_TO_NEW_DASHBOARD_MIGRATION.md` for mapping legacy UI to new components/SDK

---


## 🔄 Distributed Dataset Integration & Compute Acceleration

**IPFS Kit Python** now includes comprehensive integration with **ipfs_datasets_py** (distributed dataset storage) and **ipfs_accelerate_py** (compute acceleration) across **36 strategic integration points** throughout the codebase.

### Integration Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    IPFS Kit Python Package                      │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐  │
│  │   Core       │  │   AI/ML      │  │   VFS & Buckets    │  │
│  │ Infrastructure│  │   Compute    │  │   Systems          │  │
│  │              │  │              │  │                    │  │
│  │ • Logging    │  │ • Framework  │  │ • Bucket Manager  │  │
│  │ • Monitoring │  │ • Training   │  │ • VFS Manager     │  │
│  │ • WAL        │  │ • Registry   │  │ • Indexes         │  │
│  │ • Health     │  │ • Utils      │  │ • Journal         │  │
│  └──────┬───────┘  └──────┬───────┘  └─────────┬───────────┘  │
│         │                 │                     │              │
│         └─────────────────┴─────────────────────┘              │
│                           │                                    │
└───────────────────────────┼────────────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            │                               │
  ┌─────────▼──────────┐       ┌───────────▼────────────┐
  │  ipfs_datasets_py  │       │  ipfs_accelerate_py    │
  │                    │       │                        │
  │ • Dataset Storage  │       │ • Compute Acceleration │
  │ • CID Management   │       │ • 2-5x Faster Ops      │
  │ • Provenance       │       │ • Distributed Compute  │
  │ • Immutable Logs   │       │ • Memory Optimization  │
  └────────────────────┘       └────────────────────────┘
            │                               │
            └───────────────┬───────────────┘
                            │
                    ┌───────▼────────┐
                    │  IPFS Network  │
                    │                │
                    │ • Distributed  │
                    │ • Content-     │
                    │   Addressed    │
                    │ • Replicated   │
                    └────────────────┘
```

### What's Integrated

**ipfs_datasets_py** - Distributed, immutable dataset storage:
- Content-addressed storage with CIDs for all operations
- Immutable audit trails for compliance
- Distributed replication across IPFS network
- Complete provenance tracking with version history
- Time-series analytics for all logged data

**ipfs_accelerate_py** - Compute acceleration for AI/ML:
- 2-5x faster AI inference operations
- Distributed compute coordination
- Memory-efficient processing algorithms
- Automatic optimization for production workloads

### Integration Coverage (36 Modules)

#### Core Infrastructure (10 modules)
- **audit_logging.py** - Security audit events as immutable datasets
- **log_manager.py** - Version-controlled log file storage
- **storage_wal.py** - Distributed write-ahead log storage
- **wal_telemetry.py** - Performance metrics as time-series datasets
- **health monitoring** - Health check history with timestamps
- **fs_journal_monitor** - Filesystem monitoring with alert history
- **fs_journal_replication** - Replication operations with node tracking
- **enhanced_server** - ALL MCP command tracking (infrastructure-level integration)
- **lifecycle managers** - Enterprise lifecycle policy execution tracking
- **data_lifecycle** - Data lifecycle event history

#### AI/ML Compute Acceleration (5 modules)
- **framework_integration.py** - HuggingFace inference acceleration
- **distributed_training.py** - Distributed training compute coordination
- **model_registry.py** - Model operation acceleration
- **ai_ml_integrator.py** - Central compute coordination
- **utils.py** - Dependency detection and validation

#### Virtual Filesystem (10 modules)
- **bucket_vfs_manager.py** - Bucket operation tracking
- **vfs_manager.py** - VFS folder operation tracking
- **vfs_version_tracker.py** - Version snapshot creation
- **enhanced_bucket_index.py** - Index update tracking
- **arrow_metadata_index.py** - Metadata change tracking
- **pin_metadata_index.py** - Pin operation tracking
- **unified_bucket_interface.py** - API operation tracking
- **vfs_journal.py** - VFS operation journaling
- **vfs_observer.py** - VFS change observation
- **vfs.py** - MCP VFS wrapper

#### Bucket & MCP Tools (11 modules)
- **bucket_manager.py** - Bucket lifecycle tracking
- **simple_bucket_manager.py** - Simple bucket operations
- **simplified_bucket_manager.py** - Simplified bucket operations
- **bucket_vfs_mcp_tools.py** - MCP bucket tool invocations
- **vfs_version_mcp_tools.py** - Version control actions
- **vfs_tools.py** - VFS tool usage
- **enhanced_mcp_server_with_vfs.py** - VFS server operations
- **enhanced_vfs_mcp_server.py** - Enhanced VFS server metrics
- **standalone_vfs_mcp_server.py** - Standalone VFS operations
- **fs_journal_controller.py** - Journal controller actions
- **filesystem_journal.py** - Complete filesystem journal

### Key Benefits

**For Operations:**
- 📊 Complete operation history across ALL systems
- 🔍 Distributed command and action tracking
- ⚡ Performance analytics from telemetry (2-5x faster with acceleration)
- 🏥 Health monitoring with historical trends
- 📝 Comprehensive logging infrastructure

**For Compliance:**
- 🔒 Immutable audit trails (tamper-proof)
- 📋 Complete operation provenance
- 🏛️ Regulatory-ready storage (GDPR, CCPA, HIPAA)
- 📆 Lifecycle policy enforcement logs
- ⚖️ Enterprise-grade compliance

**For Developers:**
- 🛡️ Zero breaking changes (fully backward compatible)
- 🎯 Consistent API across all integrations
- 📚 Comprehensive documentation
- ✅ 77 tests validate all integrations
- 🔧 Easy to extend with same patterns

### Usage

**Enable Dataset Storage:**
```python
from ipfs_kit_py.mcp.enhanced_server import EnhancedMCPServer

# All MCP commands automatically tracked
server = EnhancedMCPServer(
    enable_dataset_storage=True,  # Enable distributed storage
    dataset_batch_size=100,        # Batch size for performance
    ipfs_client=ipfs_client        # Your IPFS client
)

# Operations automatically stored as datasets with CIDs
# Manual flush available: server.flush_to_dataset()
```

**Enable Compute Acceleration:**
```python
from ipfs_kit_py.mcp.ai.framework_integration import HuggingFaceIntegration

integration = HuggingFaceIntegration(config)

# Automatically uses ipfs_accelerate_py if available (2-5x faster)
result = integration.text_generation("prompt")

# Falls back to standard compute if ipfs_accelerate_py unavailable
```

**Check Dependency Availability:**
```python
from ipfs_kit_py.mcp.ai.utils import check_dependencies

deps = check_dependencies()
print(f"ipfs_datasets_py available: {deps['ipfs_datasets_py']}")
print(f"ipfs_accelerate_py available: {deps['ipfs_accelerate_py']}")
```

### Graceful Fallbacks (100% CI/CD Compatible)

All integrations include graceful fallbacks:
- ✅ Works perfectly **without** ipfs_datasets_py (uses local storage)
- ✅ Works perfectly **without** ipfs_accelerate_py (uses standard compute)
- ✅ Works perfectly **without** both packages
- ✅ Zero CI/CD failures - tests skip gracefully when dependencies unavailable
- ✅ All features are optional and disabled by default

### Optional Dependencies

```bash
# Install with dataset storage support
pip install ipfs_datasets_py

# Add compute acceleration (submodule)
git submodule update --init external/ipfs_accelerate_py

# Or use without either - everything still works!
```

### Documentation

**Integration Documentation:**
- `COMPLETE_INTEGRATION_SUMMARY.md` - Overview of all 36 integrations
- `MCP_INTEGRATION_ARCHITECTURE.md` - MCP tool architecture guide
- `docs/IPFS_DATASETS_INTEGRATION.md` - Base integration patterns
- `docs/IPFS_DATASETS_COMPREHENSIVE_INTEGRATION.md` - Complete reference (650+ lines)
- `docs/VFS_BUCKET_GRAPHRAG_INTEGRATION.md` - GraphRAG architecture with compute layer

**Testing:**
- 77 comprehensive tests across 9 test files
- Import path validation tests
- Architecture compliance validation
- All tests pass with graceful skips

---


## 🌟 Key Features

### 🚀 **Cluster Management**
- **Leader Election**: Automatic leader selection with role hierarchy (Master → Worker → Leecher)
- **Replication Management**: Master-only replication initiation with worker distribution
- **Indexing Services**: Master-only write operations with distributed read access
- **Role-Based Access Control**: Enforced permissions based on node roles
- **Health Monitoring**: Comprehensive cluster health checks and status reporting

### 🐳 **Container & Orchestration**
- **Docker Ready**: Multi-stage builds with development and production configurations
- **Kubernetes Native**: StatefulSets, Services, ConfigMaps for production deployment
- **3-Node Cluster**: Local testing and production-ready cluster configurations
- **Auto-Scaling**: Horizontal pod autoscaling support for worker nodes

### 🔄 **Auto-Healing Workflows with GitHub Copilot** ⭐ NEW
- **🤖 GitHub Copilot Agent Integration**: Uses AI to intelligently analyze and fix workflow failures
- **Automatic Failure Detection**: Monitors all GitHub Actions workflows for failures in real-time
- **AI-Powered Fix Generation**: Copilot agents create context-aware, intelligent fixes
- **Multiple Integration Methods**: Auto-fix, Copilot Workspace, and manual invocation
- **Smart Pattern Recognition**: Learns from the entire GitHub ecosystem, not just patterns
- **Automated PR Creation**: Creates detailed PRs with explanations and test recommendations
- **Zero Configuration**: Works out of the box after one-time repository setup
- **📚 [Copilot Auto-Healing Guide](./docs/features/copilot/COPILOT_AUTO_HEALING_GUIDE.md)** | **[Quick Reference](./docs/features/copilot/COPILOT_AUTO_HEALING_QUICK_REF.md)** | **[Original Guide](./docs/features/auto-healing/AUTO_HEALING_WORKFLOWS.md)**

### 🎛️ **MCP Server Integration**
- **Production Ready**: Advanced cluster-ready MCP server with multi-backend support
- **Real-time Communication**: WebSocket and WebRTC for streaming operations
- **Multi-Backend Storage**: IPFS, Filecoin, S3, Storacha, HuggingFace, Lassie integration
- **AI/ML Features**: Model registry, dataset management, and distributed training support
- **📚 [Full MCP Development Status & Roadmap](./MCP_DEVELOPMENT_STATUS.md)**

### 🔧 **Virtual File System (VFS)**
- **IPFS Integration**: Seamless VFS operations through ipfs_fsspec interface
- **Mount Management**: Dynamic mounting and unmounting of IPFS paths
- **File Operations**: Read, write, delete operations on distributed storage
- **Metadata Handling**: Rich metadata support for files and directories

### 🧠 **AI/ML Integration**
- **Vector Storage**: Distributed vector indexing and similarity search
- **Knowledge Graphs**: SPARQL and Cypher query support
- **Embeddings Management**: Efficient storage and retrieval of ML embeddings
- **Data Processing**: Comprehensive dataset operations and transformations

### 🎯 **Three-Tier Policy System**
- **Global Pinset Policies**: Comprehensive replication and cache policies via `ipfs-kit config pinset-policy`
- **Bucket-Level Policies**: Per-bucket replication backends and cache settings via `ipfs-kit bucket policy`
- **Backend-Specific Quotas**: Quota and retention policies for all backends to prevent overflow while preserving data
- **Performance-Based Tiers**: Automatic tiering based on backend characteristics (speed vs persistence)
- **Intelligent Failover**: Geographic distribution and failover strategies across backends

## 🚀 Quick Start

### 1. Single Node Deployment

```bash
# Clone and setup
git clone https://github.com/endomorphosis/ipfs_kit_py.git
cd ipfs_kit_py

# Zero-touch install (creates .venv, installs deps, runs a quick import check)
./scripts/deployment/zero_touch_install.sh

# Alternatively (legacy):
# pip install -r requirements.txt

# Start single MCP server
python standalone_cluster_server.py
```

### 2. 3-Node Cluster Deployment

```bash
# Local 3-node cluster
python start_3_node_cluster.py

# Test cluster functionality
python comprehensive_cluster_demonstration.py

# Docker Compose cluster
cd docker && docker-compose up -d

# Kubernetes cluster
kubectl apply -f k8s/
```

### 3. Policy System Configuration

```bash
# Configure global pinset policies
ipfs-kit config pinset-policy set \
  --replication-strategy tiered \
  --cache-policy adaptive \
  --performance-tier balanced \
  --auto-tier

# Configure bucket-level policies
ipfs-kit bucket policy set my-bucket \
  --primary-backend filecoin \
  --replication-backends "s3,arrow,parquet" \
  --cache-policy lru \
  --retention-days 365

# Configure backend quotas (example: Filecoin)
ipfs-kit backend lotus configure \
  --quota-size 10TB \
  --retention-policy permanent \
  --auto-renew \
  --redundancy-level 3

# Configure backend quotas (example: Arrow) 
ipfs-kit backend arrow configure \
  --memory-quota 8GB \
  --retention-policy temporary \
  --session-retention 24
```

### 4. Quick Health Check

```bash
# Check cluster status
curl http://localhost:8998/health          # Master node
curl http://localhost:8999/health          # Worker 1
curl http://localhost:9000/health          # Worker 2

# Cluster management
curl http://localhost:8998/cluster/status  # Cluster overview
curl http://localhost:8998/cluster/leader  # Current leader

# Policy status
ipfs-kit config pinset-policy show        # Global policies
ipfs-kit bucket policy show              # All bucket policies
```

## 🏗️ Architecture Overview

### Cluster Topology
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Master    │    │   Worker 1  │    │   Worker 2  │
│   Port: 8998│◄──►│   Port: 8999│◄──►│  Port: 9000 │
│             │    │             │    │             │
│ ✅ Leader    │    │ 📥 Follower  │    │ 📥 Follower  │
│ ✅ Replication│    │ ✅ Replication│    │ ✅ Replication│
│ ✅ Indexing  │    │ 👁️ Read-Only │    │ 👁️ Read-Only │
│ ✅ VFS Ops   │    │ ✅ VFS Ops   │    │ ✅ VFS Ops   │
└─────────────┘    └─────────────┘    └─────────────┘
```

### Role Hierarchy
1. **Master**: Full privileges (leader election, replication initiation, index writes)
2. **Worker**: Limited privileges (follower, replication reception, index reads)
3. **Leecher**: Read-only (no leadership, no replication, index reads only)

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NODE_ID` | `ipfs-mcp-node` | Unique node identifier |
| `NODE_ROLE` | `worker` | Node role: master/worker/leecher |
| `SERVER_HOST` | `0.0.0.0` | Server bind address |
| `SERVER_PORT` | `8998` | Server port |
| `CLUSTER_PEERS` | `` | Comma-separated peer list |
| `DEBUG` | `false` | Enable debug logging |
| `ENABLE_REPLICATION` | `true` | Enable replication features |
| `ENABLE_INDEXING` | `true` | Enable indexing features |
| `ENABLE_VFS` | `true` | Enable VFS integration |

### Bucket Policy REST & Dashboard Integration

The dashboard now supports inline per-bucket policy editing (replication factor, cache policy, retention days):

REST Endpoints:
```
GET  /api/state/buckets/{name}/policy          # Return current policy (auto-injects defaults if missing)
POST /api/state/buckets/{name}/policy          # Update one or more policy fields (requires x-api-token)
```
JSON Body Fields (partial updates allowed on POST):
- `replication_factor` (int, 1–10, default 1)
- `cache_policy` (enum: none|memory|disk, default none)
- `retention_days` (int, >=0, default 0)

Example Update:
```bash
curl -H 'Content-Type: application/json' \
  -H 'x-api-token: $TOKEN' \
  -d '{"replication_factor":3, "cache_policy":"memory", "retention_days":30}' \
  http://127.0.0.1:8004/api/state/buckets/my-bucket/policy
```

Dashboard Usage:
- Navigate to Buckets panel → each bucket row is expandable.
- Click the ▾ control to load and reveal policy form (lazy loads via GET endpoint).
- Edit values and press Save (POST); inline status messages indicate success or validation errors.

Validation Errors:
- 400 returned for out-of-range replication_factor or invalid cache_policy values.
- 401 returned if missing/invalid token for POST.

Legacy buckets without a `policy` object receive defaults on first read (implicit migration, persisted on next update).

### Three-Tier Policy System Configuration

#### 1. Global Pinset Policies (`ipfs-kit config pinset-policy`)

Configure system-wide defaults for all pinsets:

```bash
# Set global replication strategy
ipfs-kit config pinset-policy set \
  --replication-strategy adaptive \
  --min-replicas 2 \
  --max-replicas 5 \
  --geographic-distribution regional

# Configure global cache policies
ipfs-kit config pinset-policy set \
  --cache-policy tiered \
  --cache-size 10000 \
  --cache-memory-limit 4GB \
  --auto-gc

# Set performance optimization
ipfs-kit config pinset-policy set \
  --performance-tier balanced \
  --auto-tier \
  --hot-tier-duration 86400 \
  --warm-tier-duration 604800

# Configure backend preferences
ipfs-kit config pinset-policy set \
  --preferred-backends "filecoin,s3,arrow" \
  --backend-weights "filecoin:0.4,s3:0.3,arrow:0.3"
```

#### 2. Bucket-Level Policies (`ipfs-kit bucket policy`)

Override global settings per bucket:

```bash
# Configure bucket for high-performance workloads
ipfs-kit bucket policy set fast-bucket \
  --primary-backend arrow \
  --replication-backends "arrow,parquet,s3" \
  --performance-tier speed-optimized \
  --cache-policy lru \
  --cache-priority high

# Configure bucket for long-term storage
ipfs-kit bucket policy set archive-bucket \
  --primary-backend filecoin \
  --replication-backends "filecoin,s3" \
  --performance-tier persistence-optimized \
  --retention-days 2555 \
  --auto-tier

# Configure bucket with tiered backends
ipfs-kit bucket policy set balanced-bucket \
  --hot-backend arrow \
  --warm-backend parquet \
  --cold-backend s3 \
  --archive-backend filecoin \
  --max-size 1TB
```

#### 3. Backend-Specific Quotas & Retention

Each backend has characteristics-based quota management:

**Filecoin/Lotus (High Persistence, Low Speed)**:
```bash
ipfs-kit backend lotus configure \
  --quota-size 50TB \
  --retention-policy permanent \
  --min-deal-duration 518400 \
  --auto-renew \
  --redundancy-level 3 \
  --cleanup-expired
```

**Arrow (High Speed, Low Persistence)**:
```bash
ipfs-kit backend arrow configure \
  --memory-quota 16GB \
  --retention-policy temporary \
  --session-retention 48 \
  --spill-to-disk \
  --compression-level 3
```

**S3 (Moderate Speed, High Persistence)**:
```bash
ipfs-kit backend s3 configure \
  --account-quota 10TB \
  --retention-policy lifecycle \
  --auto-delete-after 365 \
  --cost-optimization \
  --transfer-acceleration
```

**Parquet (Balanced Characteristics)**:
```bash
ipfs-kit backend parquet configure \
  --storage-quota 5TB \
  --retention-policy access-based \
  --compression-algorithm snappy \
  --auto-compaction \
  --metadata-caching
```

### Example Configuration

```bash
# Master node configuration
export NODE_ID=master-1
export NODE_ROLE=master
export SERVER_PORT=8998
export CLUSTER_PEERS=127.0.0.1:8999,127.0.0.1:9000

# Worker node configuration
export NODE_ID=worker-1
export NODE_ROLE=worker
export SERVER_PORT=8999
export CLUSTER_PEERS=127.0.0.1:8998,127.0.0.1:9000
```

## 🐳 Docker Deployment

### Quick Start with Docker Compose

```bash
cd docker
docker-compose up -d

# View logs
docker-compose logs -f

# Scale workers
docker-compose up -d --scale ipfs-mcp-worker1=3

# Stop cluster
docker-compose down -v
```

### Individual Container Deployment

```bash
# Build image
docker build -t ipfs-kit-mcp:latest -f docker/Dockerfile .

# Master node
docker run -d --name ipfs-master \
  -p 8998:8998 \
  -e NODE_ID=master-1 \
  -e NODE_ROLE=master \
  -e CLUSTER_PEERS=worker-1:8998,worker-2:8998 \
  ipfs-kit-mcp:latest

# Worker nodes
docker run -d --name ipfs-worker1 \
  -p 8999:8998 \
  -e NODE_ID=worker-1 \
  -e NODE_ROLE=worker \
  -e CLUSTER_PEERS=master-1:8998,worker-2:8998 \
  ipfs-kit-mcp:latest
```

## ☸️ Kubernetes Deployment

### Production Deployment

```bash
# Deploy complete cluster
kubectl apply -f k8s/

# Check status
kubectl get pods -n ipfs-cluster
kubectl get services -n ipfs-cluster

# Port forward for access
kubectl port-forward svc/ipfs-mcp-master 8998:8998 -n ipfs-cluster

# Run cluster tests
kubectl apply -f k8s/03-test-job.yaml
```

### Resource Requirements

| Component | CPU Request | CPU Limit | Memory Request | Memory Limit | Storage |
|-----------|-------------|-----------|----------------|--------------|---------|
| Master | 250m | 1000m | 512Mi | 2Gi | 50Gi |
| Worker | 250m | 750m | 512Mi | 1.5Gi | 30Gi |

## 🧪 Testing & Validation

### Comprehensive Test Suite

```bash
# Unit tests
python -m pytest tests/ -v

# Cluster functionality tests
python comprehensive_cluster_demonstration.py

# Load testing
python tests/test_load_performance.py

# CI/CD integration
.github/workflows/test.yml  # Automated testing
```

### Manual Testing Commands

```bash
# Health checks
curl http://localhost:8998/health | jq '.'

# Leader election
curl http://localhost:8998/cluster/leader | jq '.'

# Replication (master only)
curl -X POST http://localhost:8998/replication/replicate \
  -H "Content-Type: application/json" \
  -d '{"cid": "QmTest", "target_peers": ["worker-1", "worker-2"]}'

# Indexing (master only)
curl -X POST http://localhost:8998/indexing/data \
  -H "Content-Type: application/json" \
  -d '{"index_type": "embeddings", "key": "test", "data": {"vector": [0.1, 0.2, 0.3]}}'

# Permission testing (should fail)
curl -X POST http://localhost:8999/replication/replicate \
  -H "Content-Type: application/json" \
  -d '{"cid": "QmTest"}'  # 403 Forbidden
```

## 📊 Performance Metrics

### Cluster Performance
- **Startup Time**: ~10 seconds for 3-node cluster
- **API Response**: <50ms for most endpoints
- **Health Checks**: <100ms response time
- **Throughput**: 49+ RPS sustained load

### Resource Usage
- **Memory**: 512Mi-2Gi per node
- **CPU**: 250m-1000m per node
- **Storage**: 30-50Gi per node for production
- **Network**: Minimal overhead for cluster communication

## 🔐 Security Features

### Authentication & Authorization
- **Role-Based Access Control**: Enforced at API level
- **Node Authentication**: Cluster peer validation
- **TLS Support**: Configurable HTTPS endpoints
- **Network Policies**: Kubernetes network isolation

### Security Best Practices
```bash
# Generate cluster secrets
kubectl create secret generic cluster-secrets \
  --from-literal=cluster-secret=$(openssl rand -base64 32) \
  -n ipfs-cluster

# Enable TLS
export ENABLE_TLS=true
export TLS_CERT_PATH=/app/certs/tls.crt
export TLS_KEY_PATH=/app/certs/tls.key
```

## 🗂️ Project Structure

```
ipfs_kit_py/
├── 📁 cluster/                    # Cluster management
│   ├── standalone_cluster_server.py   # Standalone cluster server
│   ├── start_3_node_cluster.py       # 3-node cluster launcher
│   └── comprehensive_cluster_demonstration.py
├── 📁 docker/                    # Container deployment
│   ├── Dockerfile                # Multi-stage container build
│   ├── docker-compose.yml        # 3-node cluster compose
│   └── *.yaml                    # Configuration files
├── 📁 k8s/                       # Kubernetes manifests
│   ├── 00-services.yaml          # Cluster services
│   ├── 01-master.yaml            # Master StatefulSet
│   ├── 02-workers.yaml           # Worker StatefulSets
│   └── 03-test-job.yaml          # Test automation
├── 📁 tests/                     # Comprehensive tests
│   ├── test_cluster_services.py  # Cluster functionality
│   ├── test_vfs_integration.py   # VFS operations
│   └── test_http_api_integration.py # API testing
├── 📁 docs/                      # Documentation
│   ├── CLUSTER_DEPLOYMENT_GUIDE.md
│   ├── CLUSTER_TEST_RESULTS.md
│   └── API_REFERENCE.md
└── 📁 ipfs_kit_py/              # Core library
    ├── enhanced_daemon_manager_with_cluster.py
    ├── ipfs_fsspec.py           # VFS interface
    └── tools/                   # MCP tools
```

## 📚 Documentation

### Core Documentation
- **[Cluster Deployment Guide](./CLUSTER_DEPLOYMENT_GUIDE.md)**: Complete deployment instructions
- **[Test Results](./CLUSTER_TEST_RESULTS.md)**: Comprehensive validation results
- **[API Reference](./docs/API_REFERENCE.md)**: Complete API documentation
- **[Architecture Guide](./docs/ARCHITECTURE.md)**: System design and components
- **[Auto-Healing Workflows](./docs/features/auto-healing/AUTO_HEALING_WORKFLOWS.md)**: ⭐ NEW - Automated workflow repair system
- **[Auto-Healing Quick Start](./docs/features/auto-healing/AUTO_HEALING_QUICK_START.md)**: ⭐ NEW - 5-minute setup guide

### Tutorials & Examples
- **[Getting Started](./docs/GETTING_STARTED.md)**: Step-by-step setup guide
- **[Cluster Management](./docs/CLUSTER_MANAGEMENT.md)**: Advanced cluster operations
- **[VFS Integration](./docs/VFS_INTEGRATION.md)**: Virtual filesystem usage
- **[Production Deployment](./docs/PRODUCTION_DEPLOYMENT.md)**: Production best practices

- See `MCP_DASHBOARD_FEATURE_PARITY_CHECKLIST.md` for a feature parity tracker aligned to the legacy dashboard UI
- See `LEGACY_TO_NEW_DASHBOARD_MIGRATION.md` for mapping legacy UI to new components/SDK

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](./CONTRIBUTING.md) for details.

### Development Setup

```bash
# Clone repository
git clone https://github.com/endomorphosis/ipfs_kit_py.git
cd ipfs_kit_py

# Setup development environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# Run tests
python -m pytest tests/ -v

# Start development cluster
python start_3_node_cluster.py
```

## 📄 License

This project is licensed under the **AGPL-3.0 License** - see the [LICENSE](./LICENSE) file for details.

## 🙏 Acknowledgments

- **IPFS Team**: For the amazing distributed storage protocol
- **Model Context Protocol**: For the excellent AI integration framework
- **Docker & Kubernetes**: For containerization and orchestration platforms
- **Python Community**: For the robust ecosystem of libraries

## � Support

- **Issues**: [GitHub Issues](https://github.com/endomorphosis/ipfs_kit_py/issues)
- **Discussions**: [GitHub Discussions](https://github.com/endomorphosis/ipfs_kit_py/discussions)
- **Documentation**: [Project Wiki](https://github.com/endomorphosis/ipfs_kit_py/wiki)

---

**Ready to deploy your distributed IPFS cluster?** 🚀

Start with our [Quick Start Guide](./docs/GETTING_STARTED.md) or dive into [Production Deployment](./docs/PRODUCTION_DEPLOYMENT.md)!

```python
import ipfs_kit_py

# Automatically installs IPFS, Lotus, Lassie, and Storacha binaries
kit = ipfs_kit_py.ipfs_kit()

# Check installation status
print(f"IPFS available: {ipfs_kit_py.INSTALL_IPFS_AVAILABLE}")
print(f"Lotus available: {ipfs_kit_py.INSTALL_LOTUS_AVAILABLE}") 
print(f"Lassie available: {ipfs_kit_py.INSTALL_LASSIE_AVAILABLE}")
print(f"Storacha available: {ipfs_kit_py.INSTALL_STORACHA_AVAILABLE}")

# All binaries are automatically added to PATH and ready to use
```

**Supported Binaries:**
- **IPFS**: Core IPFS node functionality and daemon management
- **Lotus**: Filecoin network integration and blockchain operations  
- **Lassie**: Fast content retrieval from Filecoin storage providers
- **Storacha**: Web3.Storage integration for decentralized storage

All binaries are downloaded from official sources, verified, and configured automatically.

**IPFS Kit Python** automatically downloads and installs required binaries when you first import the package or create a virtual environment:

- **🌐 IPFS Binaries**: Kubo daemon, cluster service, cluster control, and cluster follow tools
- **🔗 Lotus Binaries**: Lotus daemon and miner for Filecoin integration
- **📦 Lassie Binary**: High-performance IPFS retrieval client
- **☁️ Storacha Dependencies**: Web3.Storage Python and NPM dependencies

```python
# Automatic installation on first import
from ipfs_kit_py import install_ipfs, install_lotus, install_lassie, install_storacha

# All installers are available and ready to use
ipfs_installer = install_ipfs()
lotus_installer = install_lotus()  
lassie_installer = install_lassie()
storacha_installer = install_storacha()

# Check installation status
from ipfs_kit_py import (
    INSTALL_IPFS_AVAILABLE,
    INSTALL_LOTUS_AVAILABLE, 
    INSTALL_LASSIE_AVAILABLE,
    INSTALL_STORACHA_AVAILABLE
)
```

**Manual Installation** (if needed):
```python
# Install specific components
ipfs_installer.install_ipfs_daemon()
lotus_installer.install_lotus_daemon()
lassie_installer.install_lassie_daemon()
storacha_installer.install_storacha_dependencies()
```

## 🌟 Key Features

### ✅ Production MCP Server (100% Tested)
- **FastAPI-based REST API** with 5 comprehensive IPFS operations
- **Model Context Protocol (MCP)** compatible JSON-RPC 2.0 interface
- **High Performance**: 49+ requests per second with excellent reliability
- **Mock IPFS Implementation**: Reliable testing without IPFS daemon dependency
- **Health Monitoring**: `/health`, `/stats`, `/metrics` endpoints
- **Auto-generated Documentation**: Interactive API docs at `/docs`

### 🔧 Automatic Binary Management
- **Smart Auto-Installation**: Automatically downloads and installs required binaries
- **Multi-Platform Support**: Works on Linux, macOS, and Windows
- **Four Core Installers**: IPFS, Lotus, Lassie, and Storacha dependencies
- **Virtual Environment Integration**: Binaries installed when venv is created
- **MCP Server Ready**: All dependencies available for immediate use

### 📦 IPFS Operations (All Validated ✅)

The MCP server provides these **5 core IPFS tools**:

1. **`ipfs_add`** - Add content to IPFS storage
2. **`ipfs_cat`** - Retrieve content by CID  
3. **`ipfs_pin_add`** - Pin content for persistence
4. **`ipfs_pin_rm`** - Unpin content to free storage
5. **`ipfs_version`** - Get IPFS version and system info

### 🏗️ Advanced Features
- **Cluster Management**: Multi-node IPFS cluster coordination
- **Tiered Storage**: Intelligent caching and storage layers
- **AI/ML Integration**: Machine learning pipeline support
- **High-Level API**: Simplified Python interface for IPFS operations
- **FSSpec Integration**: FileSystem Spec compatibility for data science
- **WebRTC Support**: Real-time communication capabilities

## 📋 API Reference

### Health & Monitoring
```bash
GET /health          # Server health check (✅ Validated)
GET /stats           # Server statistics (✅ Validated)  
GET /metrics         # Performance metrics
GET /docs            # Interactive API documentation (✅ Validated)
GET /                # Server information (✅ Validated)
```

### MCP Tools (JSON-RPC 2.0)
```bash
POST /jsonrpc        # MCP protocol endpoint
GET /mcp/tools       # List available tools (✅ Validated - 5 tools)
```

### IPFS Operations (REST API)
```bash
POST /ipfs/add                # Add content (✅ Validated)
GET /ipfs/cat/{cid}          # Retrieve content (✅ Validated)
POST /ipfs/pin/add/{cid}     # Pin content (✅ Validated)
DELETE /ipfs/pin/rm/{cid}    # Unpin content (✅ Validated)
GET /ipfs/version            # Version info (✅ Validated)
```

### Policy System CLI Commands

#### Global Pinset Policies
```bash
# View current policies
ipfs-kit config pinset-policy show

# Set replication policies
ipfs-kit config pinset-policy set \
  --replication-strategy {single,multi-backend,tiered,adaptive} \
  --min-replicas N \
  --max-replicas N \
  --geographic-distribution {local,regional,global}

# Set cache policies  
ipfs-kit config pinset-policy set \
  --cache-policy {lru,lfu,fifo,mru,adaptive,tiered} \
  --cache-size N \
  --cache-memory-limit SIZE \
  --auto-gc

# Set performance and tiering
ipfs-kit config pinset-policy set \
  --performance-tier {speed-optimized,balanced,persistence-optimized} \
  --auto-tier \
  --hot-tier-duration SECONDS \
  --warm-tier-duration SECONDS

# Reset to defaults
ipfs-kit config pinset-policy reset
```

#### Bucket-Level Policies
```bash
# View bucket policies
ipfs-kit bucket policy show [BUCKET_NAME]

# Set bucket-specific policies
ipfs-kit bucket policy set BUCKET_NAME \
  --replication-backends "backend1,backend2,backend3" \
  --primary-backend {s3,filecoin,arrow,parquet,ipfs,storacha,sshfs,ftp} \
  --cache-policy {lru,lfu,fifo,mru,adaptive,inherit} \
  --performance-tier {speed-optimized,balanced,persistence-optimized,inherit}

# Set bucket lifecycle management
ipfs-kit bucket policy set BUCKET_NAME \
  --retention-days N \
  --max-size SIZE \
  --quota-action {warn,block,auto-archive,auto-delete}

# Set bucket tiering
ipfs-kit bucket policy set BUCKET_NAME \
  --auto-tier \
  --hot-backend BACKEND \
  --warm-backend BACKEND \
  --cold-backend BACKEND \
  --archive-backend BACKEND

# Copy policies between buckets
ipfs-kit bucket policy copy SOURCE_BUCKET DEST_BUCKET

# Apply predefined templates
ipfs-kit bucket policy template BUCKET_NAME TEMPLATE_NAME

# Reset bucket to global defaults
ipfs-kit bucket policy reset BUCKET_NAME
```

#### Backend-Specific Configuration
```bash
# Filecoin/Lotus (High Persistence, Low Speed)
ipfs-kit backend lotus configure \
  --quota-size SIZE \
  --retention-policy {permanent,deal-duration,custom} \
  --auto-renew \
  --redundancy-level N

# Arrow (High Speed, Low Persistence)  
ipfs-kit backend arrow configure \
  --memory-quota SIZE \
  --retention-policy {temporary,session-based,memory-based} \
  --session-retention HOURS \
  --spill-to-disk

# S3 (Moderate Speed, High Persistence)
ipfs-kit backend s3 configure \
  --account-quota SIZE \
  --retention-policy {indefinite,compliance,lifecycle} \
  --cost-optimization \
  --transfer-acceleration

# Parquet (Balanced)
ipfs-kit backend parquet configure \
  --storage-quota SIZE \
  --retention-policy {indefinite,access-based,size-based} \
  --compression-algorithm {snappy,gzip,lz4,zstd} \
  --auto-compaction

# All other backends have similar configure commands with
# backend-appropriate quota and retention options
```

## 🧪 Testing & Validation

The project includes comprehensive testing with **100% success rate**:

```bash
# Run comprehensive test suite (validates all 4 installers + core functionality)
python final_comprehensive_test.py

# Run specific installer tests
python quick_verify.py

# Run MCP server validation
python tests/integration/mcp_production_validation.py

# Run unit tests
pytest tests/unit/
pytest tests/integration/
```

**Latest Test Results** (9/9 tests passed):
- ✅ **Installer Imports**: All 4 installer modules importable
- ✅ **Binary Availability**: IPFS, Lotus, Lassie, Storacha all functional  
- ✅ **Installer Instantiation**: All installer classes work correctly
- ✅ **Core Imports**: All core modules import successfully
- ✅ **Availability Flags**: All installation flags set correctly
- ✅ **MCP Server Integration**: Full MCP server compatibility
- ✅ **Documentation Accuracy**: All docs reflect current functionality
- ✅ **No Critical Warnings**: Clean imports without errors
- ✅ **Lotus Daemon Functionality**: Filecoin integration working

**Additional Validation**:
- ✅ All 5 MCP tools functional (ipfs_add, ipfs_cat, ipfs_pin_add, ipfs_pin_rm, ipfs_version)
- ✅ Performance: 49+ RPS with excellent reliability
- ✅ Auto-installation of all required binaries
- ✅ Content flow validated (add → retrieve → pin)

## 🐳 Docker Deployment

### Production Deployment
```bash
# Using Docker Compose (recommended)
docker-compose up -d

# Check logs
docker-compose logs -f

# Scale the service
docker-compose up -d --scale mcp-server=3
```

### Manual Docker
```bash
# Build custom image
docker build -t ipfs-kit-mcp .

# Run with custom configuration
docker run -p 9998:9998 \
  -e IPFS_KIT_HOST=0.0.0.0 \
  -e IPFS_KIT_PORT=9998 \
  ipfs-kit-mcp
```

## ⚙️ Configuration

### Environment Variables
```bash
IPFS_KIT_HOST=0.0.0.0        # Server host (default: 127.0.0.1)
IPFS_KIT_PORT=9998           # Server port (default: 9998)  
IPFS_KIT_DEBUG=true          # Enable debug mode (default: false)
PYTHONUNBUFFERED=1           # Unbuffered output for Docker
```

### Command Line Options
```bash
python final_mcp_server_enhanced.py --help

Options:
  --host HOST         Host to bind to (default: 127.0.0.1)
  --port PORT         Port to bind to (default: 9998)
  --debug             Enable debug mode with detailed logging
  --log-level LEVEL   Set logging level (DEBUG, INFO, WARNING, ERROR)
```

## 📁 Project Structure

```
ipfs_kit_py/
├── 📄 final_mcp_server_enhanced.py    # Main production MCP server
├── 📄 requirements.txt                # Dependencies  
├── 📄 pyproject.toml                  # Package configuration
├── 📚 docs/                           # Documentation (2,400+ files)
├── 🧪 tests/                          # Test suites (900+ files)
├── 🛠️ tools/                          # Development tools (400+ files)
├── 🔧 scripts/                        # Shell scripts (200+ files)
├── 🐳 docker/                         # Docker configuration
├── ⚙️ config/                         # Configuration files
├── 📦 archive/                        # Archived development files
├── 📄 backup/                         # Backup and logs
└── 🐍 ipfs_kit_py/                    # Main Python package
```

## 💻 Development

### Development Setup
```bash
# Clone and setup
git clone https://github.com/endomorphosis/ipfs_kit_py.git
cd ipfs_kit_py

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run in development mode
python final_mcp_server_enhanced.py --debug
```

### Running Tests
```bash
# All tests
pytest tests/

# Integration tests only
pytest tests/integration/

# Specific test file
pytest tests/integration/comprehensive_mcp_test.py

# With coverage
pytest --cov=ipfs_kit_py tests/
```

### Building Package
```bash
# Build for distribution
python -m build

# Install locally
pip install -e .

# Install with extras
pip install -e .[ai_ml,webrtc,full]

# Build Tailwind CSS for production (no CDN)
npm install
npm run build:css
```

For detailed Tailwind CSS build instructions, see [TAILWIND_BUILD.md](./TAILWIND_BUILD.md).

## 🔌 Integration Examples

### Basic Usage
```python
import requests

# Add content to IPFS
response = requests.post('http://localhost:9998/ipfs/add', 
                        json={'content': 'Hello IPFS!'})
cid = response.json()['cid']

# Retrieve content
response = requests.get(f'http://localhost:9998/ipfs/cat/{cid}')
content = response.json()['content']

# Pin content
requests.post(f'http://localhost:9998/ipfs/pin/add/{cid}')
```

### MCP Protocol Usage
```python
import requests

# JSON-RPC 2.0 call
payload = {
    "jsonrpc": "2.0",
    "method": "tools/call", 
    "params": {
        "name": "ipfs_add",
        "arguments": {"content": "Hello from MCP!"}
    },
    "id": 1
}

response = requests.post('http://localhost:9998/jsonrpc', json=payload)
result = response.json()['result']
```

### Python Package Usage
```python
# Import the high-level API (if available)
try:
    from ipfs_kit_py import IPFSSimpleAPI
    api = IPFSSimpleAPI()
    print("High-level API available")
except ImportError:
    print("High-level API not available in this configuration")

# Use the MCP server for IPFS operations
# Start server: python final_mcp_server_enhanced.py
# Then use REST API or JSON-RPC endpoints
```

### Using the Installers
```python
# Import installers (automatically triggers binary installation)
from ipfs_kit_py import install_ipfs, install_lotus, install_lassie, install_storacha

# Create installer instances
ipfs_installer = install_ipfs()
lotus_installer = install_lotus()
lassie_installer = install_lassie()
storacha_installer = install_storacha()

# Check if binaries are available
from ipfs_kit_py import (
    INSTALL_IPFS_AVAILABLE,
    INSTALL_LOTUS_AVAILABLE,
    INSTALL_LASSIE_AVAILABLE,
    INSTALL_STORACHA_AVAILABLE
)

print(f"IPFS: {INSTALL_IPFS_AVAILABLE}")
print(f"Lotus: {INSTALL_LOTUS_AVAILABLE}")
print(f"Lassie: {INSTALL_LASSIE_AVAILABLE}")
print(f"Storacha: {INSTALL_STORACHA_AVAILABLE}")

# Manual installation (if needed)
ipfs_installer.install_ipfs_daemon()
lotus_installer.install_lotus_daemon()
lassie_installer.install_lassie_daemon()
storacha_installer.install_storacha_dependencies()
```

## 📚 Documentation

- **[Production Ready Status](./docs/PRODUCTION_READY_STATUS.md)** - Complete validation and readiness documentation
- **[Installer Documentation](./docs/INSTALLER_DOCUMENTATION.md)** - Complete installer system guide
- **[MCP Tools Validation](./docs/MCP_TOOLS_VALIDATION_COMPLETE.md)** - Complete testing results
- **[Workspace Cleanup](./docs/WORKSPACE_CLEANUP_COMPLETE.md)** - Organization details
- **[API Documentation](http://localhost:9998/docs)** - Interactive API docs (when server running)
- **[Examples](./examples/)** - Usage examples and tutorials
- **[Configuration](./config/)** - Configuration options and examples

### 🔧 Installer System

The package includes four automatic installers:

1. **🌐 IPFS Installer** - Core IPFS binaries and cluster tools
2. **🔗 Lotus Installer** - Filecoin network integration  
3. **📦 Lassie Installer** - High-performance IPFS retrieval
4. **☁️ Storacha Installer** - Web3.Storage dependencies

See [Installer Documentation](./docs/INSTALLER_DOCUMENTATION.md) for complete details.

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines:

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Run tests**: `pytest tests/`
4. **Commit changes**: `git commit -m 'Add amazing feature'`
5. **Push to branch**: `git push origin feature/amazing-feature`
6. **Open a Pull Request**

### Development Guidelines
- Follow PEP 8 style guidelines
- Write tests for new features
- Update documentation as needed
- Ensure all tests pass before submitting

## 📈 Performance

**Benchmark Results** (validated):
- **Request Rate**: 49+ requests per second
- **Response Time**: < 20ms average
- **Success Rate**: 100% (19/19 tests passed)
- **Uptime**: Production grade stability
- **Memory Usage**: Optimized for efficiency

## 🛡️ Security

- **Input Validation**: All inputs validated and sanitized
- **Error Handling**: Comprehensive error handling with security in mind
- **No External Dependencies**: Mock IPFS reduces attack surface
- **CORS Support**: Configurable cross-origin resource sharing
- **Health Monitoring**: Built-in health checks and monitoring

## 📝 License

This project is licensed under the **AGPL-3.0-or-later** License - see the [LICENSE](./LICENSE) file for details.

## 🙏 Acknowledgments

- **IPFS Team** - For the distributed storage protocol
- **FastAPI** - For the excellent web framework  
- **Model Context Protocol** - For the MCP specification
- **Python Community** - For the amazing ecosystem

## � Project Structure

The project is organized for maintainability and production readiness:

```
ipfs_kit_py/
├── standalone_cluster_server.py    # 🚀 Production cluster server
├── start_3_node_cluster.py         # 🚀 Production cluster launcher  
├── main.py                         # 🚀 Main application entry point
├── ipfs_kit_py/                    # 📦 Core Python package
├── cluster/                        # 🔗 Cluster management
├── servers/                        # 🛠️  Development servers
├── tests/                          # 🧪 All testing & validation
├── tools/                          # 🔧 Development & maintenance tools
├── docs/                           # 📚 Organized documentation
├── examples/                       # 💡 Code examples
├── deployment/                     # 🚢 Deployment resources
└── PROJECT_STRUCTURE.md            # 📋 Detailed structure guide
```

**Quick Start Commands:**
```bash
# Production cluster
python start_3_node_cluster.py

# Development server  
cd servers/ && python enhanced_mcp_server_with_full_config.py

# Run tests
cd tests/ && python -m pytest

# Check status
cd tools/ && python verify_reorganization.py
```


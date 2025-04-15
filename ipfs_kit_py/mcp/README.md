# MCP Server Architecture Overview

## Introduction

This document provides a comprehensive overview of the Model-Controller-Persistence (MCP) server architecture after the Q2 2025 consolidation. It explains how all components work together to provide a unified interface for interacting with various distributed storage systems.

## Architecture Components

The MCP server follows a structured architecture with clear separation of concerns:

```
ipfs_kit_py/mcp/
├── __init__.py               # Main module initialization
├── direct_mcp_server.py      # Primary entry point
├── storage_manager/          # Unified Storage Manager
│   ├── __init__.py
│   ├── backend_base.py       # Backend interface
│   ├── backend_manager.py    # Manager for multiple backends
│   ├── storage_types.py      # Type definitions
│   └── backends/             # Storage backend implementations
│       ├── ipfs_backend.py   # IPFS backend (fixed)
│       ├── s3_backend.py     # S3 backend
│       ├── filecoin_backend.py # Filecoin backend
│       └── ...
├── migration/                # Cross-Backend Migration
│   ├── __init__.py
│   └── migration_controller.py # Policy-based migration
├── search/                   # Search Integration
│   ├── __init__.py
│   └── mcp_search.py         # Text and vector search
└── streaming/                # Streaming Operations
    ├── __init__.py
    ├── file_streaming.py     # Chunked file operations
    ├── websocket_notifications.py # Real-time events
    └── webrtc_signaling.py   # P2P connections
```

## Component Interactions

### 1. Core Components

#### Unified Storage Manager

The storage manager provides a consistent interface for interacting with different storage backends:

- **Abstract Interface**: `BackendStorage` defines a common interface
- **Backend Manager**: `BackendManager` manages multiple storage backends
- **Backend Types**: Supported backends include IPFS, S3, Filecoin, Storacha, HuggingFace, and Lassie

Key features:
- Uniform content addressing across backends
- Cross-backend content reference system
- Content-aware backend selection

#### IPFS Backend Implementation

The IPFS backend connects to IPFS networks:

- **Fixed Dependency**: The `ipfs_py` client is properly available and imported
- **Robust Import Mechanism**: Multiple fallback approaches ensure reliability
- **Comprehensive API**: Full support for content operations, pinning, and metadata

Key improvements:
- Enhanced import mechanism with dynamic module loading
- Proper error handling and graceful degradation
- Comprehensive monitoring of operations

### 2. Advanced Features

#### Cross-Backend Migration

The migration controller enables policy-based content migration between storage backends:

- **Policies**: Define rules for when and how content should migrate
- **Tasks**: Individual migration operations with tracking
- **Scheduler**: Background processing of migration tasks

Key capabilities:
- Cost optimization with predictive analysis
- Verification and integrity checking
- Priority-based migration queue

#### Search Integration

The search functionality provides advanced content discovery:

- **Content Indexing**: Automated metadata extraction and text indexing
- **Text Search**: Full-text search with SQLite FTS5
- **Vector Search**: Semantic similarity with FAISS and sentence-transformers
- **Hybrid Search**: Combined text and vector search with relevance ranking

#### Streaming Operations

The streaming components enable efficient content transfer and real-time communication:

- **File Streaming**: Chunked uploads and memory-optimized downloads
- **WebSocket**: Real-time notifications and event broadcasting
- **WebRTC Signaling**: Peer-to-peer connection establishment

Key features:
- Progress tracking for all operations
- Background pinning for large files
- Channel-based subscription system

## API Endpoints

The MCP server exposes a comprehensive API for all functionality:

| Category | Base Path | Description |
|----------|-----------|-------------|
| IPFS | `/api/v0/ipfs/*` | Core IPFS operations |
| Storage | `/api/v0/storage/*` | Multi-backend storage operations |
| Filecoin | `/api/v0/filecoin/advanced/*` | Advanced Filecoin features |
| Search | `/api/v0/search/*` | Text and vector search |
| Streaming | `/api/v0/stream/*` | File streaming operations |
| Real-time | `/api/v0/realtime/*` | Real-time notifications |
| WebRTC | `/api/v0/webrtc/*` | WebRTC signaling |
| WebSocket | `/ws` | WebSocket connections |

## Verification Framework

The following verification tools ensure all components work correctly:

| Script | Purpose |
|--------|---------|
| `scripts/verify_ipfs_dependency.py` | Verifies IPFS backend dependency resolution |
| `scripts/verify_migration_controller.py` | Tests cross-backend migration functionality |
| `scripts/verify_search_integration.py` | Validates search functionality |
| `scripts/verify_streaming.py` | Tests streaming operations |
| `scripts/verify_api_endpoints.py` | Verifies all API endpoints are accessible |
| `run_integration_tests.py` | Runs comprehensive integration tests |

## Usage Examples

### 1. Multi-Backend Storage

```python
from ipfs_kit_py.mcp.storage_manager.backend_manager import BackendManager
from ipfs_kit_py.mcp.storage_manager.storage_types import StorageBackendType

# Initialize backend manager
manager = BackendManager()

# Add content to IPFS
result = manager.add_content(
    backend_type=StorageBackendType.IPFS,
    content="Hello, IPFS!"
)

# Store same content in S3
s3_result = manager.add_content(
    backend_type=StorageBackendType.S3,
    content="Hello, IPFS!",
    reference=result.get("identifier")  # Link to IPFS version
)
```

### 2. Cross-Backend Migration

```python
from ipfs_kit_py.mcp.migration import MigrationController, MigrationPolicy

# Initialize controller with backend manager
controller = MigrationController(backend_manager=manager)

# Create migration policy
policy = MigrationPolicy(
    name="ipfs_to_filecoin",
    source_backend="ipfs",
    destination_backend="filecoin",
    content_filter={"min_size": 1024 * 1024}  # Files over 1MB
)

# Add policy
controller.add_policy(policy)

# Execute policy
task_ids = controller.execute_policy("ipfs_to_filecoin")
```

### 3. Search Integration

```python
from ipfs_kit_py.mcp.search import SearchEngine

# Initialize search engine
engine = SearchEngine(enable_vector_search=True)

# Index content
await engine.index_document(
    cid="QmExample",
    text="This is an example document about IPFS.",
    metadata={"type": "documentation"}
)

# Search by text
results = await engine.search_text("IPFS example")

# Search by semantic similarity
vector_results = await engine.search_vector("distributed storage")
```

### 4. Streaming Operations

```python
from ipfs_kit_py.mcp.streaming import ChunkedFileUploader, ProgressTracker

# Create uploader
uploader = ChunkedFileUploader(chunk_size=1024*1024)

# Create progress tracker
tracker = ProgressTracker()

# Upload large file with progress tracking
result = await uploader.upload(
    file_path="/path/to/large/file",
    destination=ipfs_backend,
    progress_tracker=tracker
)

# Get progress information
progress_info = tracker.get_info()
```

## Conclusion

The MCP server architecture has been successfully consolidated and enhanced, with all components verified and fully functional. The modular design enables seamless interaction between different storage backends, while advanced features like migration, search, and streaming provide a comprehensive solution for distributed content management.

Future development will focus on the roadmap items outlined in the MCP Roadmap document, including AI/ML integration, enterprise features, and edge computing capabilities.
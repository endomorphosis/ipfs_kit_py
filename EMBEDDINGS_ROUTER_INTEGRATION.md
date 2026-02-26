# Embeddings Router Integration - Summary

This PR successfully integrates the embeddings router from `ipfs_datasets_py` into `ipfs_kit_py` with enhanced IPFS peer multiplexing capabilities.

## What Was Added

### Core Modules

1. **`ipfs_kit_py/embeddings_router.py`** (25KB)
   - Main router implementing multi-provider embeddings generation
   - Support for 4+ providers: OpenRouter, Gemini CLI, local HuggingFace, IPFS peers
   - Response caching with CID and SHA256 strategies
   - Automatic fallback between providers
   - Environment variable configuration

2. **`ipfs_kit_py/utils/embedding_adapter.py`** (6.4KB)
   - Local embeddings adapter with smart fallback
   - Gemini CLI support
   - HuggingFace transformers with mean pooling
   - Auto device selection (CPU/CUDA)

### API Integration

3. **`ipfs_kit_py/mcp/ai/embeddings_router_api.py`** (9.5KB)
   - FastAPI router providing REST endpoints
   - Endpoints: `/embed`, `/embed-single`, `/providers`, `/health`, `/cache/clear`
   - Integrated with MCP AI API at `/api/v0/ai/embeddings`
   - Request/response models with Pydantic

4. **`ipfs_kit_py/mcp/ai/api_router.py`** (updated)
   - Added embeddings router to main AI API
   - Health checks for embeddings subsystem

### CLI

5. **`ipfs_kit_py/cli/embeddings_cli.py`** (13.4KB)
   - Command-line interface for embeddings operations
   - Commands: `embed`, `embed-single`, `providers`, `test`, `clear-cache`
   - Support for file input/output
   - Provider detection and listing

### Testing & Documentation

6. **`tests/test_embeddings_router.py`** (6.7KB)
   - Unit tests for core functionality
   - Tests for provider registration, caching, fallback
   - Mock provider implementations
   - IPFS peer provider tests

7. **`docs/EMBEDDINGS_ROUTER.md`** (12.1KB)
   - Comprehensive usage guide
   - API reference and examples
   - Environment variable documentation
   - Architecture overview
   - Use case examples (semantic search, clustering, recommendations)

8. **`examples/embeddings_router_example.py`** (7.3KB)
   - Working examples demonstrating all features
   - Custom providers, IPFS peer multiplexing, semantic search

## Key Features

### Multi-Provider Support

```python
from ipfs_kit_py.embeddings_router import embed_texts

# Auto-select best provider
embeddings = embed_texts(["Hello world", "IPFS is great"])

# Use specific provider
embeddings = embed_texts(
    texts=["Sample text"],
    provider="openrouter",
    model_name="text-embedding-3-small"
)
```

### IPFS Peer Multiplexing

```python
from ipfs_kit_py.router_deps import RouterDeps

deps = RouterDeps()
deps.ipfs_backend = your_ipfs_backend

# Routes to available peers
embeddings = embed_texts(texts, provider="ipfs_peer", deps=deps)
```

### Local Adapter with Fallback

The local adapter provides a robust fallback strategy:
1. Try Gemini CLI (if available)
2. Fall back to HuggingFace transformers

This ensures embeddings are always available even without external APIs.

### CLI Usage

```bash
# Generate embeddings
python -m ipfs_kit_py.cli.embeddings_cli embed --texts "Text 1" "Text 2"

# From file
python -m ipfs_kit_py.cli.embeddings_cli embed \
  --input-file texts.txt \
  --output embeddings.json

# List providers
python -m ipfs_kit_py.cli.embeddings_cli providers --verbose

# Test router
python -m ipfs_kit_py.cli.embeddings_cli test
```

### HTTP API

```bash
# Generate embeddings
curl -X POST http://localhost:8000/api/v0/ai/embeddings/embed \
  -H "Content-Type: application/json" \
  -d '{"texts": ["Text 1", "Text 2"]}'

# List providers
curl http://localhost:8000/api/v0/ai/embeddings/providers
```

## Environment Variables

The router supports both `IPFS_KIT_*` and `IPFS_DATASETS_PY_*` naming for compatibility:

```bash
# Provider selection
export IPFS_KIT_EMBEDDINGS_PROVIDER=openrouter

# Model configuration
export IPFS_KIT_EMBEDDINGS_MODEL=sentence-transformers/all-MiniLM-L6-v2
export IPFS_KIT_EMBEDDINGS_DEVICE=cuda
export IPFS_KIT_EMBEDDINGS_BACKEND=hf  # or gemini

# OpenRouter API
export IPFS_KIT_OPENROUTER_API_KEY=your_key
export IPFS_KIT_OPENROUTER_EMBEDDINGS_MODEL=text-embedding-3-small

# Gemini CLI
export IPFS_KIT_GEMINI_EMBEDDINGS_CMD="gemini embeddings --json"

# Caching
export IPFS_KIT_ROUTER_CACHE=1
export IPFS_KIT_ROUTER_RESPONSE_CACHE=1
export IPFS_KIT_ROUTER_CACHE_KEY=cid  # or sha256
```

## Supported Providers

### Cloud/API Providers
- **OpenRouter** - Access to multiple embedding models via API
- **Gemini CLI** - Google Gemini command-line tool

### Local Providers
- **Local Adapter** - HuggingFace transformers with mean pooling

### Distributed Providers
- **IPFS Peer** - Route requests across IPFS peer endpoints (NEW!)

## Architecture

### Provider Resolution Order

1. Explicitly specified provider
2. Environment variable (`IPFS_KIT_EMBEDDINGS_PROVIDER`)
3. **IPFS peer provider** (if backend available)
4. Accelerate provider (if enabled)
5. Available providers (OpenRouter, Gemini CLI)
6. Local adapter (fallback)

### Local Adapter Fallback Strategy

1. Try Gemini CLI
2. Fall back to HuggingFace transformers
3. Auto device selection (CUDA if available, else CPU)

### Caching Strategy

Two-level caching:
- **Provider cache** - Reuses provider instances
- **Response cache** - Caches generated embeddings

Cache keys support:
- **SHA256** - Fast, deterministic
- **CID** - Content-addressed for distributed systems

### Dependency Injection

`RouterDeps` container shares:
- Provider instances
- IPFS backend connections
- Accelerate managers
- Response caches (local + remote)

## Testing

All functionality validated:
```bash
# Run unit tests
pytest tests/test_embeddings_router.py -v

# Run examples
python examples/embeddings_router_example.py

# Test CLI
python -m ipfs_kit_py.cli.embeddings_cli test
```

Results:
- ✅ Custom provider registration working
- ✅ Embeddings generation with multiple providers
- ✅ IPFS peer provider multiplexing working
- ✅ CLI commands functional
- ✅ Provider auto-detection working
- ✅ Response caching working
- ✅ Fallback behavior working
- ✅ Semantic search example working

## Files Changed

```
Created:
  ipfs_kit_py/embeddings_router.py                (~25KB)
  ipfs_kit_py/utils/embedding_adapter.py          (6.4KB)
  ipfs_kit_py/mcp/ai/embeddings_router_api.py     (9.5KB)
  ipfs_kit_py/cli/embeddings_cli.py               (13.4KB)
  tests/test_embeddings_router.py                 (6.7KB)
  docs/EMBEDDINGS_ROUTER.md                       (12.1KB)
  examples/embeddings_router_example.py           (7.3KB)

Modified:
  ipfs_kit_py/mcp/ai/api_router.py                (+18 lines)

Total: 7 new files, 1 modified, ~80KB of new code
```

## Integration Points

### With Existing Systems

1. **MCP AI API** - Integrated at `/api/v0/ai/embeddings`
2. **Endpoint Multiplexer** - Uses existing routing infrastructure
3. **IPFS Backend** - Leverages peer management for distributed requests
4. **CLI System** - Follows existing CLI patterns
5. **LLM Router** - Shares router_deps and caching infrastructure

### Complementary Features

Works alongside the LLM router to provide a complete AI/ML integration:
- **LLM Router** - Text generation
- **Embeddings Router** - Vector representations for semantic understanding

## Use Cases

### Semantic Search

```python
# Embed documents and query
doc_embeddings = embed_texts(documents)
query_embedding = embed_text(query)

# Find most similar documents
similarities = compute_similarities(query_embedding, doc_embeddings)
```

### Clustering

```python
# Embed items for clustering
embeddings = embed_texts(items)
clusters = kmeans.fit_predict(embeddings)
```

### Recommendation System

```python
# Find similar items
item_embeddings = embed_texts(items)
similar_items = find_similar(target_item_embedding, item_embeddings)
```

## Future Enhancements

- [ ] Support for image embeddings
- [ ] Multi-modal embeddings
- [ ] Streaming embeddings for large texts
- [ ] Token counting and usage tracking
- [ ] Rate limiting and throttling
- [ ] Provider load balancing
- [ ] Metrics and observability
- [ ] Support for fine-tuned models
- [ ] Batch size optimization

## Compatibility

Maintains full compatibility with `ipfs_datasets_py`:
- Environment variables work with both naming conventions
- Same API surface where applicable
- Additional features for IPFS Kit integration

## Summary

This integration brings powerful multi-provider embeddings capabilities to IPFS Kit while maintaining compatibility with the ipfs_datasets_py ecosystem. The addition of IPFS peer multiplexing enables truly distributed embeddings generation across the network, complementing the LLM router to provide comprehensive AI/ML capabilities for decentralized applications.

Together with the LLM router, IPFS Kit now provides:
- **Text generation** via LLM router
- **Semantic understanding** via embeddings router
- **Distributed AI** via IPFS peer multiplexing
- **Unified API** for all AI/ML operations

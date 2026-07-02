# Embeddings Router Integration

The IPFS Kit Embeddings Router provides a unified interface for generating embeddings across multiple providers and IPFS peer endpoints.

## Overview

The Embeddings router is adapted from `ipfs_datasets_py` and enhanced with IPFS Kit's endpoint multiplexing capabilities. It provides:

- **Multi-provider support**: OpenRouter, Gemini CLI, and local HuggingFace models
- **Automatic fallback**: If a provider fails, automatically falls back to alternative providers
- **Response caching**: Caches embeddings for improved performance
- **Peer-to-peer routing**: Can multiplex embeddings requests across IPFS peers
- **Environment configuration**: Flexible configuration via environment variables
- **CLI and API access**: Both command-line and HTTP API interfaces

## Supported Providers

### Cloud Providers

| Provider | Description | Required |
|----------|-------------|----------|
| `openrouter` | OpenRouter API for embeddings | `OPENROUTER_API_KEY` |
| `gemini_cli` | Gemini CLI embeddings command | `gemini` command or npx |

### Local Providers

| Provider | Description | Required |
|----------|-------------|----------|
| `local_adapter` | HuggingFace Transformers (local) | `transformers` and `torch` packages |

### Distributed Providers

| Provider | Description | Required |
|----------|-------------|----------|
| `ipfs_peer` | IPFS peer endpoints via multiplexer | IPFS backend with peer manager |

## Environment Variables

### Provider Selection

```bash
# Force a specific provider
export IPFS_KIT_EMBEDDINGS_PROVIDER=openrouter

# Or use ipfs_datasets_py compatibility
export IPFS_DATASETS_PY_EMBEDDINGS_PROVIDER=openrouter
```

### Model Configuration

```bash
# Model name for local adapter
export IPFS_KIT_EMBEDDINGS_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Device for local adapter (cpu/cuda)
export IPFS_KIT_EMBEDDINGS_DEVICE=cuda

# Backend selection (gemini/hf)
export IPFS_KIT_EMBEDDINGS_BACKEND=hf

# OpenRouter specific
export IPFS_KIT_OPENROUTER_EMBEDDINGS_MODEL=text-embedding-3-small
export IPFS_KIT_OPENROUTER_API_KEY=your_key_here
export IPFS_KIT_OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

### CLI Commands

```bash
# Gemini CLI embeddings command
export IPFS_KIT_GEMINI_EMBEDDINGS_CMD="gemini embeddings --json"
```

### Caching

```bash
# Enable/disable caching
export IPFS_KIT_ROUTER_CACHE=1

# Enable response caching
export IPFS_KIT_ROUTER_RESPONSE_CACHE=1

# Cache key strategy: sha256 or cid
export IPFS_KIT_ROUTER_CACHE_KEY=sha256
```

## Usage

### Python API

#### Basic Embeddings Generation

```python
from ipfs_kit_py.embeddings_router import embed_texts, embed_text

# Generate embeddings for multiple texts
texts = ["Hello world", "IPFS is great"]
embeddings = embed_texts(texts)
print(f"Generated {len(embeddings)} embeddings")
print(f"Dimension: {len(embeddings[0])}")

# Generate embedding for single text
text = "Sample text"
embedding = embed_text(text)
print(f"Embedding dimension: {len(embedding)}")
```

#### With Specific Provider

```python
from ipfs_kit_py.embeddings_router import embed_texts

# Use OpenRouter
embeddings = embed_texts(
    texts=["Text 1", "Text 2"],
    provider="openrouter",
    model_name="text-embedding-3-small"
)

# Use Gemini CLI
embeddings = embed_texts(
    texts=["Text 1", "Text 2"],
    provider="gemini_cli"
)

# Use local HuggingFace
embeddings = embed_texts(
    texts=["Text 1", "Text 2"],
    provider="local_adapter",
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    device="cuda"
)
```

#### With Custom Provider Instance

```python
from ipfs_kit_py.embeddings_router import embed_texts, get_embeddings_provider

# Get a provider instance
provider = get_embeddings_provider("openrouter")

# Use it multiple times
for batch in text_batches:
    embeddings = embed_texts(batch, provider_instance=provider)
    process_embeddings(embeddings)
```

#### With Router Dependencies

```python
from ipfs_kit_py.embeddings_router import embed_texts
from ipfs_kit_py.router_deps import RouterDeps

# Create shared dependencies
deps = RouterDeps()

# Use across multiple calls (shares caches and connections)
embeddings1 = embed_texts(["First batch"], deps=deps)
embeddings2 = embed_texts(["Second batch"], deps=deps)
```

#### Register Custom Provider

```python
from ipfs_kit_py.embeddings_router import register_embeddings_provider

class MyCustomEmbedder:
    def embed_texts(self, texts, *, model_name=None, device=None, **kwargs):
        # Your custom implementation
        return [[0.1, 0.2, 0.3] for _ in texts]

# Register it
register_embeddings_provider("my_embedder", lambda: MyCustomEmbedder())

# Use it
embeddings = embed_texts(["test"], provider="my_embedder")
```

### CLI Usage

#### Generate Embeddings

```bash
# Basic embedding generation
python -m ipfs_kit_py.cli.embeddings_cli embed --texts "Hello world" "Another text"

# From file (one text per line)
python -m ipfs_kit_py.cli.embeddings_cli embed \
  --input-file texts.txt \
  --output embeddings.json

# With specific provider and model
python -m ipfs_kit_py.cli.embeddings_cli embed \
  --texts "Sample text" \
  --provider openrouter \
  --model text-embedding-3-small

# With device specification
python -m ipfs_kit_py.cli.embeddings_cli embed \
  --texts "Sample text" \
  --provider local_adapter \
  --device cuda \
  --verbose
```

#### Single Text Embedding

```bash
# Embed single text
python -m ipfs_kit_py.cli.embeddings_cli embed-single \
  --text "Sample text" \
  --output embedding.json

# From file
python -m ipfs_kit_py.cli.embeddings_cli embed-single \
  --input-file input.txt \
  --output embedding.json \
  --verbose
```

#### List Providers

```bash
# List available providers
python -m ipfs_kit_py.cli.embeddings_cli providers

# With detailed information
python -m ipfs_kit_py.cli.embeddings_cli prov --verbose
```

#### Test Router

```bash
# Quick test
python -m ipfs_kit_py.cli.embeddings_cli test

# Test specific provider
python -m ipfs_kit_py.cli.embeddings_cli test --provider openrouter
```

#### Clear Caches

```bash
# Clear all caches
python -m ipfs_kit_py.cli.embeddings_cli clear-cache
```

### HTTP API

The embeddings router is integrated into the MCP AI API at `/api/v0/ai/embeddings`.

#### Generate Embeddings

```bash
curl -X POST http://localhost:8000/api/v0/ai/embeddings/embed \
  -H "Content-Type: application/json" \
  -d '{
    "texts": ["Hello world", "IPFS is great"],
    "model_name": "text-embedding-3-small",
    "provider": "openrouter"
  }'
```

#### Generate Single Embedding

```bash
curl -X POST http://localhost:8000/api/v0/ai/embeddings/embed-single \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Sample text",
    "device": "cuda"
  }'
```

#### List Providers

```bash
curl http://localhost:8000/api/v0/ai/embeddings/providers
```

#### Health Check

```bash
curl http://localhost:8000/api/v0/ai/embeddings/health
```

#### Clear Cache

```bash
curl -X POST http://localhost:8000/api/v0/ai/embeddings/cache/clear
```

## IPFS Peer Multiplexing

The embeddings router integrates with IPFS Kit's endpoint multiplexer to route requests across peer endpoints:

```python
from ipfs_kit_py.embeddings_router import embed_texts
from ipfs_kit_py.router_deps import RouterDeps

# Create deps with IPFS backend
deps = RouterDeps()
deps.ipfs_backend = your_ipfs_backend_instance

# This will automatically use peer endpoints if available
embeddings = embed_texts(
    texts=["Generate embeddings"],
    provider="ipfs_peer",  # Explicitly use peer routing
    deps=deps
)
```

## Architecture

### Provider Resolution

The router resolves providers in the following order:

1. **Explicitly specified provider** - If `provider` parameter is set
2. **Environment variable** - `IPFS_KIT_EMBEDDINGS_PROVIDER`
3. **IPFS peer provider** - If IPFS backend is available
4. **Accelerate provider** - If IPFS accelerate is enabled
5. **Available providers** - OpenRouter, Gemini CLI
6. **Local adapter** - HuggingFace transformers (final fallback)

### Local Adapter Fallback

The local adapter uses a smart fallback strategy:
1. Try Gemini CLI (if available)
2. Fall back to HuggingFace transformers

This ensures embeddings are always available even without external APIs.

### Caching Strategy

The router uses a two-level caching system:

1. **Provider cache** - Reuses provider instances to avoid re-initialization
2. **Response cache** - Caches generated embeddings to avoid duplicate API calls

Cache keys can use two strategies:
- **SHA256** (default): Fast, deterministic string-based keys
- **CID**: Content-addressed identifiers for distributed caching

### Dependency Injection

The `RouterDeps` container allows sharing:
- Provider instances
- IPFS backend connections
- Accelerate managers
- Response caches (local and remote)

## Error Handling

The router implements automatic fallback on errors:

```python
try:
    embeddings = embed_texts(
        texts,
        provider="openrouter",
        model_name="specific-model"
    )
except Exception:
    # Router will try local adapter fallback
    # Finally raise if all providers fail
    pass
```

## Performance Considerations

### Caching

Enable response caching for repeated texts:

```bash
export IPFS_KIT_ROUTER_RESPONSE_CACHE=1
```

### Batch Processing

Process texts in batches for better performance:

```python
# Good: batch processing
embeddings = embed_texts(all_texts)

# Less efficient: one at a time
embeddings = [embed_text(text) for text in all_texts]
```

### Provider Reuse

Reuse provider instances when making multiple calls:

```python
provider = get_embeddings_provider("openrouter")
for batch in batches:
    embeddings = embed_texts(batch, provider_instance=provider)
```

### Peer Routing

Use IPFS peer routing to distribute load:

```python
deps = RouterDeps()
deps.ipfs_backend = backend

# Automatically routes to available peers
embeddings = embed_texts(texts, deps=deps)
```

## Testing

Run the embeddings router tests:

```bash
pytest tests/test_embeddings_router.py -v
```

## Compatibility

The embeddings router maintains compatibility with `ipfs_datasets_py` environment variables:

- `IPFS_DATASETS_PY_EMBEDDINGS_PROVIDER` → `IPFS_KIT_EMBEDDINGS_PROVIDER`
- `IPFS_DATASETS_PY_EMBEDDINGS_MODEL` → `IPFS_KIT_EMBEDDINGS_MODEL`
- etc.

Both naming conventions work, with `IPFS_KIT_` taking precedence.

## Use Cases

### Semantic Search

```python
from ipfs_kit_py.embeddings_router import embed_texts

# Embed documents
documents = ["Doc 1", "Doc 2", "Doc 3"]
doc_embeddings = embed_texts(documents)

# Embed query
query = "Search query"
query_embedding = embed_text(query)

# Compute similarities
import numpy as np
similarities = [
    np.dot(query_embedding, doc_emb) / 
    (np.linalg.norm(query_embedding) * np.linalg.norm(doc_emb))
    for doc_emb in doc_embeddings
]
```

### Clustering

```python
from ipfs_kit_py.embeddings_router import embed_texts
from sklearn.cluster import KMeans

texts = [...list of texts...]
embeddings = embed_texts(texts)

# Cluster embeddings
kmeans = KMeans(n_clusters=5)
clusters = kmeans.fit_predict(embeddings)
```

### Recommendation System

```python
from ipfs_kit_py.embeddings_router import embed_texts

# Embed items
items = ["Item 1", "Item 2", "Item 3"]
item_embeddings = embed_texts(items)

# Find similar items
def find_similar(item_index, top_k=3):
    target_emb = item_embeddings[item_index]
    similarities = compute_similarities(target_emb, item_embeddings)
    return np.argsort(similarities)[-top_k:]
```

## Future Enhancements

- [ ] Support for image embeddings
- [ ] Multi-modal embeddings
- [ ] Streaming embeddings for large texts
- [ ] Token counting and usage tracking
- [ ] Rate limiting and throttling
- [ ] Provider load balancing
- [ ] Metrics and observability integration
- [ ] Support for fine-tuned models
- [ ] Batch size optimization

## See Also

- [LLM Router](./LLM_ROUTER.md)
- [MCP AI Integration](./MCP_AI_INTEGRATION.md)
- [IPFS Datasets Integration](./IPFS_DATASETS_INTEGRATION.md)
- [Endpoint Multiplexing](./ENDPOINT_MULTIPLEXING.md)

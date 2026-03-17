# LLM Router Integration

The IPFS Kit LLM Router provides a unified interface for text generation across multiple LLM providers and IPFS peer endpoints.

## Overview

The LLM router is adapted from `ipfs_datasets_py` and enhanced with IPFS Kit's endpoint multiplexing capabilities. It provides:

- **Multi-provider support**: OpenRouter, GitHub Copilot, Codex, Gemini, Claude, and local HuggingFace models
- **Automatic fallback**: If a provider fails, automatically falls back to alternative providers
- **Response caching**: Caches responses for improved performance and reduced costs
- **Peer-to-peer routing**: Can multiplex LLM requests across IPFS peers
- **Environment configuration**: Flexible configuration via environment variables
- **CLI and API access**: Both command-line and HTTP API interfaces

## Supported Providers

### Cloud Providers

| Provider | Description | Required |
|----------|-------------|----------|
| `openrouter` | OpenRouter API for access to multiple models | `OPENROUTER_API_KEY` |
| `copilot_sdk` | GitHub Copilot Python SDK | `copilot` package |
| `copilot_cli` | GitHub Copilot CLI | `npx @github/copilot` or custom command |
| `codex_cli` | OpenAI Codex CLI | `codex` command |
| `gemini_cli` | Google Gemini CLI | `npx @google/gemini-cli` or custom command |
| `gemini_py` | Gemini Python wrapper | Built-in wrapper |
| `claude_code` | Claude Code CLI | `claude` command or custom command |
| `claude_py` | Claude Python wrapper | Built-in wrapper |

### Local Providers

| Provider | Description | Required |
|----------|-------------|----------|
| `local_hf` | HuggingFace Transformers (local) | `transformers` package |

### Distributed Providers

| Provider | Description | Required |
|----------|-------------|----------|
| `ipfs_peer` | IPFS peer endpoints via multiplexer | IPFS backend with peer manager |

## Environment Variables

### Provider Selection

```bash
# Force a specific provider
export IPFS_KIT_LLM_PROVIDER=openrouter

# Or use ipfs_datasets_py compatibility
export IPFS_DATASETS_PY_LLM_PROVIDER=openrouter
```

### Model Configuration

```bash
# Default model name
export IPFS_KIT_LLM_MODEL=gpt2

# OpenRouter specific
export IPFS_KIT_OPENROUTER_MODEL=openai/gpt-4o-mini
export IPFS_KIT_OPENROUTER_API_KEY=your_key_here
export IPFS_KIT_OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Copilot SDK
export IPFS_KIT_COPILOT_SDK_MODEL=gpt-4
export IPFS_KIT_COPILOT_SDK_TIMEOUT=120

# Codex CLI
export IPFS_KIT_CODEX_CLI_MODEL=gpt-5.1-codex-mini
export IPFS_KIT_CODEX_SANDBOX=read-only
```

### CLI Commands

```bash
# Custom CLI commands (support {prompt} placeholder)
export IPFS_KIT_COPILOT_CLI_CMD="npx --yes @github/copilot -p {prompt}"
export IPFS_KIT_GEMINI_CLI_CMD="npx @google/gemini-cli {prompt}"
export IPFS_KIT_CLAUDE_CODE_CLI_CMD="claude {prompt}"
```

### Caching

```bash
# Enable/disable caching
export IPFS_KIT_ROUTER_CACHE=1

# Enable response caching (default: off, enabled in benchmarks)
export IPFS_KIT_ROUTER_RESPONSE_CACHE=1

# Cache key strategy: sha256 or cid
export IPFS_KIT_ROUTER_CACHE_KEY=sha256

# CID base encoding for cid strategy
export IPFS_KIT_ROUTER_CACHE_CID_BASE=base32
```

### IPFS Accelerate

```bash
# Enable IPFS accelerate integration
export IPFS_KIT_ENABLE_IPFS_ACCELERATE=1
```

## Usage

### Python API

#### Basic Text Generation

```python
from ipfs_kit_py.llm_router import generate_text

# Simple generation with auto provider selection
text = generate_text("Write a haiku about IPFS")
print(text)

# Use a specific provider
text = generate_text(
    "Explain distributed systems",
    provider="openrouter",
    model_name="openai/gpt-4o-mini",
    max_tokens=500,
    temperature=0.7
)
```

#### With Custom Provider Instance

```python
from ipfs_kit_py.llm_router import generate_text, get_llm_provider

# Get a provider instance
provider = get_llm_provider("openrouter")

# Use it multiple times
for prompt in prompts:
    text = generate_text(prompt, provider_instance=provider)
    print(text)
```

#### With Router Dependencies

```python
from ipfs_kit_py.llm_router import generate_text
from ipfs_kit_py.router_deps import RouterDeps

# Create shared dependencies
deps = RouterDeps()

# Use across multiple calls (shares caches and connections)
text1 = generate_text("First prompt", deps=deps)
text2 = generate_text("Second prompt", deps=deps)
```

#### Register Custom Provider

```python
from ipfs_kit_py.llm_router import register_llm_provider

class MyCustomProvider:
    def generate(self, prompt: str, *, model_name=None, **kwargs):
        # Your custom implementation
        return "Generated text"

# Register it
register_llm_provider("my_provider", lambda: MyCustomProvider())

# Use it
text = generate_text("Test prompt", provider="my_provider")
```

### CLI Usage

#### Generate Text

```bash
# Basic generation
python -m ipfs_kit_py.cli.llm_cli generate --prompt "Write a haiku about IPFS"

# With specific provider and model
python -m ipfs_kit_py.cli.llm_cli gen \
  --prompt "Explain distributed systems" \
  --provider openrouter \
  --model openai/gpt-4o-mini \
  --max-tokens 500

# From file with output
python -m ipfs_kit_py.cli.llm_cli g \
  --prompt-file input.txt \
  --output result.txt
```

#### List Providers

```bash
# List available providers
python -m ipfs_kit_py.cli.llm_cli providers

# With detailed information
python -m ipfs_kit_py.cli.llm_cli prov --verbose
```

#### Test Router

```bash
# Quick test
python -m ipfs_kit_py.cli.llm_cli test

# Test specific provider
python -m ipfs_kit_py.cli.llm_cli test --provider openrouter
```

#### Clear Caches

```bash
# Clear all caches
python -m ipfs_kit_py.cli.llm_cli clear-cache
```

### HTTP API

The LLM router is integrated into the MCP AI API at `/api/v0/ai/llm`.

#### Generate Text

```bash
curl -X POST http://localhost:8000/api/v0/ai/llm/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Write a haiku about IPFS",
    "max_tokens": 100,
    "temperature": 0.7
  }'
```

#### List Providers

```bash
curl http://localhost:8000/api/v0/ai/llm/providers
```

#### Health Check

```bash
curl http://localhost:8000/api/v0/ai/llm/health
```

#### Clear Cache

```bash
curl -X POST http://localhost:8000/api/v0/ai/llm/cache/clear
```

## IPFS Peer Multiplexing

The LLM router integrates with IPFS Kit's endpoint multiplexer to route requests across peer endpoints:

```python
from ipfs_kit_py.llm_router import generate_text
from ipfs_kit_py.router_deps import RouterDeps

# Create deps with IPFS backend
deps = RouterDeps()
deps.ipfs_backend = your_ipfs_backend_instance

# This will automatically use peer endpoints if available
text = generate_text(
    "Generate text",
    provider="ipfs_peer",  # Explicitly use peer routing
    deps=deps
)
```

## Architecture

### Provider Resolution

The router resolves providers in the following order:

1. **Explicitly specified provider** - If `provider` parameter is set
2. **Environment variable** - `IPFS_KIT_LLM_PROVIDER`
3. **IPFS peer provider** - If IPFS backend is available
4. **Accelerate provider** - If IPFS accelerate is enabled
5. **Available CLI/API providers** - OpenRouter, Copilot, Codex, Gemini, Claude
6. **Local HuggingFace** - As final fallback

### Caching Strategy

The router uses a two-level caching system:

1. **Provider cache** - Reuses provider instances to avoid re-initialization
2. **Response cache** - Caches generated text to avoid duplicate API calls

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
    text = generate_text(
        prompt,
        model_name="specific-model"
    )
except Exception:
    # Router will try with default model
    # Then try local HuggingFace fallback
    # Finally raise if all providers fail
    pass
```

## Performance Considerations

### Caching

Enable response caching for repeated prompts:

```bash
export IPFS_KIT_ROUTER_RESPONSE_CACHE=1
```

### Provider Reuse

Reuse provider instances when making multiple calls:

```python
provider = get_llm_provider("openrouter")
for prompt in many_prompts:
    text = generate_text(prompt, provider_instance=provider)
```

### Peer Routing

Use IPFS peer routing to distribute load:

```python
deps = RouterDeps()
deps.ipfs_backend = backend

# Automatically routes to available peers
text = generate_text(prompt, deps=deps)
```

## Testing

Run the LLM router tests:

```bash
pytest tests/test_llm_router.py -v
```

## Compatibility

The LLM router maintains compatibility with `ipfs_datasets_py` environment variables:

- `IPFS_DATASETS_PY_LLM_PROVIDER` → `IPFS_KIT_LLM_PROVIDER`
- `IPFS_DATASETS_PY_LLM_MODEL` → `IPFS_KIT_LLM_MODEL`
- etc.

Both naming conventions work, with `IPFS_KIT_` taking precedence.

## Future Enhancements

- [ ] Support for streaming responses
- [ ] Token counting and usage tracking
- [ ] Rate limiting and throttling
- [ ] Provider load balancing
- [ ] Metrics and observability integration
- [ ] Support for function calling / tools
- [ ] Image generation providers
- [ ] Multi-modal support

## See Also

- [MCP AI Integration](./MCP_AI_INTEGRATION.md)
- [IPFS Datasets Integration](./IPFS_DATASETS_INTEGRATION.md)
- [Endpoint Multiplexing](./ENDPOINT_MULTIPLEXING.md)

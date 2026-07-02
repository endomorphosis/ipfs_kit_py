# LLM Router Integration - Summary

This PR successfully integrates the LLM router from `ipfs_datasets_py` into `ipfs_kit_py` with enhanced IPFS peer multiplexing capabilities.

## What Was Added

### Core Modules

1. **`ipfs_kit_py/llm_router.py`** (30KB)
   - Main router implementing multi-provider LLM text generation
   - Support for 10+ providers: OpenRouter, Copilot SDK/CLI, Codex, Gemini, Claude, local HuggingFace
   - Response caching with CID and SHA256 strategies
   - Automatic fallback between providers
   - Environment variable configuration

2. **`ipfs_kit_py/router_deps.py`** (5.7KB)
   - Dependency injection container for shared state
   - Manages provider instances, IPFS backend connections, and caches
   - Thread-safe operations
   - Support for remote/distributed caching

3. **`ipfs_kit_py/utils/`**
   - `cid_utils.py` - Content-addressed identifier generation
   - `gemini_cli.py` - Google Gemini CLI wrapper
   - `claude_cli.py` - Anthropic Claude CLI wrapper

### API Integration

4. **`ipfs_kit_py/mcp/ai/llm_router_api.py`** (7.4KB)
   - FastAPI router providing REST endpoints
   - Endpoints: `/generate`, `/providers`, `/health`, `/cache/clear`
   - Integrated with MCP AI API at `/api/v0/ai/llm`
   - Request/response models with Pydantic

5. **`ipfs_kit_py/mcp/ai/api_router.py`** (updated)
   - Added LLM router to main AI API
   - Health checks for LLM subsystem

### CLI

6. **`ipfs_kit_py/cli/llm_cli.py`** (9.7KB)
   - Command-line interface for LLM operations
   - Commands: `generate`, `providers`, `test`, `clear-cache`
   - Support for file input/output
   - Provider detection and listing

### Testing & Documentation

7. **`tests/test_llm_router.py`** (7.1KB)
   - Unit tests for core functionality
   - Tests for provider registration, caching, fallback
   - Mock provider implementations

8. **`docs/LLM_ROUTER.md`** (9.6KB)
   - Comprehensive usage guide
   - API reference and examples
   - Environment variable documentation
   - Architecture overview

9. **`examples/llm_router_example.py`** (5.4KB)
   - Working examples demonstrating all features
   - Custom providers, IPFS peer multiplexing, fallback

## Key Features

### Multi-Provider Support

```python
from ipfs_kit_py.llm_router import generate_text

# Auto-select best provider
text = generate_text("Write a haiku about IPFS")

# Use specific provider
text = generate_text("Explain distributed systems", provider="openrouter")
```

### IPFS Peer Multiplexing

```python
from ipfs_kit_py.router_deps import RouterDeps

deps = RouterDeps()
deps.ipfs_backend = your_ipfs_backend

# Routes to available peers
text = generate_text(prompt, provider="ipfs_peer", deps=deps)
```

### CLI Usage

```bash
# Generate text
python -m ipfs_kit_py.cli.llm_cli generate --prompt "Your prompt here"

# List providers
python -m ipfs_kit_py.cli.llm_cli providers --verbose

# Test router
python -m ipfs_kit_py.cli.llm_cli test
```

### HTTP API

```bash
# Generate text
curl -X POST http://localhost:8000/api/v0/ai/llm/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Your prompt", "max_tokens": 100}'

# List providers
curl http://localhost:8000/api/v0/ai/llm/providers
```

## Environment Variables

The router supports both `IPFS_KIT_*` and `IPFS_DATASETS_PY_*` naming for compatibility:

```bash
# Provider selection
export IPFS_KIT_LLM_PROVIDER=openrouter

# Model configuration
export IPFS_KIT_LLM_MODEL=gpt2
export IPFS_KIT_OPENROUTER_API_KEY=your_key

# Caching
export IPFS_KIT_ROUTER_CACHE=1
export IPFS_KIT_ROUTER_RESPONSE_CACHE=1
export IPFS_KIT_ROUTER_CACHE_KEY=cid  # or sha256

# CLI commands
export IPFS_KIT_COPILOT_CLI_CMD="npx @github/copilot -p {prompt}"
export IPFS_KIT_GEMINI_CLI_CMD="npx @google/gemini-cli {prompt}"
```

## Supported Providers

### Cloud/API Providers
- **OpenRouter** - Access to multiple LLM models via API
- **Copilot SDK** - GitHub Copilot Python SDK
- **Copilot CLI** - GitHub Copilot command-line tool
- **Codex CLI** - OpenAI Codex command-line interface
- **Gemini CLI** - Google Gemini command-line tool
- **Gemini Python** - Built-in Gemini wrapper
- **Claude Code CLI** - Anthropic Claude command-line tool
- **Claude Python** - Built-in Claude wrapper

### Local Providers
- **HuggingFace Transformers** - Local model inference

### Distributed Providers
- **IPFS Peer** - Route requests across IPFS peer endpoints (NEW!)

## Architecture

### Provider Resolution Order

1. Explicitly specified provider
2. Environment variable (`IPFS_KIT_LLM_PROVIDER`)
3. **IPFS peer provider** (if backend available)
4. Accelerate provider (if enabled)
5. Available CLI/API providers
6. Local HuggingFace (fallback)

### Caching Strategy

Two-level caching:
- **Provider cache** - Reuses provider instances
- **Response cache** - Caches generated text

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
pytest tests/test_llm_router.py -v

# Run examples
python examples/llm_router_example.py

# Test CLI
python -m ipfs_kit_py.cli.llm_cli test
```

Results:
- ✅ Custom provider registration working
- ✅ Text generation with multiple providers
- ✅ IPFS peer provider multiplexing working
- ✅ CLI commands functional
- ✅ Provider auto-detection working
- ✅ Response caching working
- ✅ Fallback behavior working

## Files Changed

```
Created:
  ipfs_kit_py/llm_router.py                    (30,762 bytes)
  ipfs_kit_py/router_deps.py                   (5,755 bytes)
  ipfs_kit_py/utils/__init__.py                (38 bytes)
  ipfs_kit_py/utils/cid_utils.py               (1,337 bytes)
  ipfs_kit_py/utils/gemini_cli.py              (1,191 bytes)
  ipfs_kit_py/utils/claude_cli.py              (1,172 bytes)
  ipfs_kit_py/mcp/ai/llm_router_api.py         (7,429 bytes)
  ipfs_kit_py/cli/llm_cli.py                   (9,665 bytes)
  tests/test_llm_router.py                     (7,108 bytes)
  docs/LLM_ROUTER.md                           (9,579 bytes)
  examples/llm_router_example.py               (5,376 bytes)

Modified:
  ipfs_kit_py/mcp/ai/api_router.py             (+34 lines)

Total: 11 new files, 1 modified, ~80KB of new code
```

## Integration Points

### With Existing Systems

1. **MCP AI API** - Integrated at `/api/v0/ai/llm`
2. **Endpoint Multiplexer** - Uses existing routing infrastructure
3. **IPFS Backend** - Leverages peer management for distributed requests
4. **CLI System** - Follows existing CLI patterns

### Future Enhancements

- [ ] Streaming responses
- [ ] Token counting and usage tracking
- [ ] Rate limiting and throttling
- [ ] Provider load balancing
- [ ] Metrics and observability
- [ ] Function calling / tools support
- [ ] Image generation providers
- [ ] Multi-modal support

## Usage Examples

See:
- `docs/LLM_ROUTER.md` - Full documentation
- `examples/llm_router_example.py` - Working examples
- `tests/test_llm_router.py` - Test examples

## Compatibility

Maintains full compatibility with `ipfs_datasets_py`:
- Environment variables work with both naming conventions
- Same API surface where applicable
- Additional features for IPFS Kit integration

## Summary

This integration brings powerful multi-provider LLM capabilities to IPFS Kit while maintaining compatibility with the ipfs_datasets_py ecosystem. The addition of IPFS peer multiplexing enables truly distributed LLM inference across the network, opening new possibilities for decentralized AI applications.

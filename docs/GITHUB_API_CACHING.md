# GitHub API Caching for Auto-Healing

The auto-healing system includes built-in caching for GitHub API calls using the IPFS Kit's caching infrastructure. This reduces API rate limit usage and enables faster duplicate issue detection.

## Features

- **Local Disk Caching**: Content-addressed storage for GitHub API responses
- **IPFS Integration**: Optional IPFS-based caching for distributed cache sharing
- **P2P Cache Sharing**: Share cache entries via libp2p gossipsub protocol
- **Intelligent TTLs**: Command-specific cache durations optimized for different data types
- **Write-through**: Write operations bypass cache, reads use cache

## Configuration

### Enable IPFS Caching

```bash
export GH_CACHE_IPFS=1
export IPFS_KIT_AUTO_HEAL=true
export GITHUB_TOKEN=your_token
export GITHUB_REPOSITORY=owner/repo
```

### Enable P2P Caching

```bash
export GH_CACHE_P2P=1
export IPFS_KIT_AUTO_HEAL=true
```

### Check Cache Status

```bash
ipfs-kit autoheal status
```

Output:
```
Auto-Healing Status:
  Enabled: Yes
  Configured: Yes
  Repository: endomorphosis/ipfs_kit_py
  GitHub Token: Set
  Auto-create issues: Yes
  Max log lines: 100
  Issue labels: auto-heal, cli-error, automated-issue

GitHub API Cache:
  Enabled: Yes
  IPFS Caching: Yes
  P2P Caching: No
  Cache Hits: 42
  Cache Misses: 8
```

## How It Works

### Cache TTLs

Different types of GitHub data have different cache durations:

| Data Type | TTL | Example Commands |
|-----------|-----|------------------|
| Immutable | 1 year | `gh commit view`, `gh release view` |
| Repository | 1 hour | `gh repo view`, `gh repo list` |
| Workflow Runs | 5 minutes | `gh run list`, `gh run view` |
| PRs | 2 minutes | `gh pr list`, `gh pr view` |
| Issues | 2 minutes | `gh issue list`, `gh issue view` |

### Write Operations

Write operations are **never cached** and always go directly to GitHub:
- Creating issues, PRs, releases
- Commenting, editing, closing
- Setting secrets/variables
- Running workflows

### Duplicate Detection

When checking for duplicate issues, the system:

1. **First try**: Use cached `gh issue list` command
2. **Fallback**: Direct GitHub API call if cache unavailable
3. **Result**: Significant reduction in API calls for frequent checks

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│           GitHubIssueCreator                            │
│                                                         │
│   check_duplicate_issue()                               │
│          │                                              │
│          ├──► GHCache (if enabled)                      │
│          │      │                                       │
│          │      ├──► Local Disk Cache                   │
│          │      │      (SHA256-based keys)              │
│          │      │                                       │
│          │      ├──► IPFS Cache (optional)              │
│          │      │      (Content-addressed)              │
│          │      │                                       │
│          │      └──► P2P Cache (optional)               │
│          │           (Gossipsub sharing)                │
│          │                                              │
│          └──► GitHub API (fallback)                     │
│                                                         │
│   create_issue_from_error()                             │
│          │                                              │
│          └──► GitHub API (never cached)                 │
└─────────────────────────────────────────────────────────┘
```

## Cache Storage

### Local Cache

Location: `~/.ipfs_kit/gh_cache/`

Structure:
```
~/.ipfs_kit/gh_cache/
├── index.json                    # Cache index with metadata
├── <sha256_hash1>.txt           # Cached response 1
├── <sha256_hash2>.txt           # Cached response 2
└── ...
```

### IPFS Cache

When IPFS caching is enabled:
- Cache entries are also stored in IPFS
- CIDs are tracked in the index
- Entries can be retrieved from any IPFS node
- Immutable by design

### P2P Cache

When P2P caching is enabled:
- Cache entries are shared via gossipsub
- Peers can request cache entries from each other
- Reduces load on GitHub API across team
- Automatic cache propagation

## Benefits

### Reduced API Rate Limits

GitHub API has rate limits:
- **Authenticated**: 5,000 requests/hour
- **Unauthenticated**: 60 requests/hour

With caching:
- Duplicate checks use cache (no API calls)
- Issue listings cached for 2 minutes
- Can handle 100s of auto-heal events/hour

### Faster Response Times

| Operation | Without Cache | With Cache |
|-----------|---------------|------------|
| Duplicate check (cache hit) | 200-500ms | <10ms |
| Duplicate check (IPFS) | 200-500ms | 50-100ms |
| Duplicate check (P2P) | 200-500ms | 20-50ms |

### Offline Capability

With IPFS/P2P caching:
- Read-only operations work offline
- Cache shared across disconnected networks
- Eventual consistency via P2P sync

## Examples

### Basic Usage (Auto-enabled)

```python
from ipfs_kit_py.auto_heal import AutoHealConfig, GitHubIssueCreator

config = AutoHealConfig(
    enabled=True,
    github_repo='owner/repo'
)

# Cache is automatically enabled
creator = GitHubIssueCreator(config)

# This uses cache if available
duplicate = creator.check_duplicate_issue(error)
```

### Explicit Cache Control

```python
# Disable cache
creator = GitHubIssueCreator(config, enable_cache=False)

# Check cache stats
stats = creator.get_cache_stats()
print(f"Cache hits: {stats['stats']['hits']}")
print(f"IPFS enabled: {stats['ipfs_enabled']}")
```

### Environment Configuration

```bash
# Enable all caching features
export GH_CACHE_IPFS=1
export GH_CACHE_P2P=1
export GH_CACHE_DEBUG=1  # Enable debug logging

# Enable auto-healing
export IPFS_KIT_AUTO_HEAL=true
export GITHUB_TOKEN=ghp_xxx
export GITHUB_REPOSITORY=owner/repo

# Run CLI with caching
ipfs-kit autoheal status
```

## Performance Tuning

### Cache Size

Default maximum cache size: 1GB (not yet enforced)

Future: Implement LRU eviction policy

### P2P Configuration

Configure gossipsub for optimal performance:

```python
# In your config
peer_config = {
    'gossipsub_d': 6,          # Desired peer connections
    'gossipsub_dlo': 4,        # Low watermark
    'gossipsub_dhi': 12,       # High watermark
    'heartbeat_interval': 1.0, # Seconds
}
```

### IPFS Configuration

Use local IPFS daemon for best performance:

```bash
ipfs daemon &
export IPFS_API=/ip4/127.0.0.1/tcp/5001
```

## Troubleshooting

### Cache Not Working

Check status:
```bash
ipfs-kit autoheal status
```

Verify Python module:
```bash
python3 -c "from ipfs_kit_py.gh_cache import GHCache; print('Cache available')"
```

### IPFS Cache Errors

Check IPFS daemon:
```bash
ipfs id
```

Fallback to local cache:
```bash
unset GH_CACHE_IPFS
```

### P2P Cache Issues

Check libp2p availability:
```bash
python3 -c "from ipfs_kit_py.libp2p.peer_manager import Libp2pPeerManager; print('P2P available')"
```

### Debug Mode

Enable verbose logging:
```bash
export GH_CACHE_DEBUG=1
ipfs-kit autoheal status
```

## Security Considerations

### Token Storage

- Tokens are **never cached**
- Cached responses don't contain sensitive auth data
- Cache keys are SHA256 hashes (no plaintext commands)

### Cache Poisoning

- IPFS cache is content-addressed (tamper-evident)
- P2P cache uses authenticated gossipsub
- Local cache has file permissions (user-only)

### Rate Limiting

- Write operations bypass cache (no amplification)
- Cache respects TTLs (no stale data abuse)
- Fallback to API if cache unavailable

## Future Enhancements

1. **Cache Eviction**: LRU policy with configurable max size
2. **Cache Warming**: Pre-populate cache for common queries
3. **Distributed Consistency**: Sync cache updates via P2P
4. **Analytics**: Track cache performance and hit rates
5. **Smart TTLs**: Adaptive TTLs based on data volatility

## References

- [GitHub API Rate Limiting](https://docs.github.com/en/rest/overview/resources-in-the-rest-api#rate-limiting)
- [IPFS Documentation](https://docs.ipfs.io/)
- [libp2p Gossipsub Spec](https://github.com/libp2p/specs/blob/master/pubsub/gossipsub/README.md)
- [IPFS Kit Caching](../ipfs_kit_py/gh_cache.py)

---

**Note**: IPFS and P2P caching are optional features. The system works perfectly with local disk caching only.

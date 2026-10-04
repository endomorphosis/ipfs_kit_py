#!/usr/bin/env python3
"""
GitHub CLI Caching Layer with IPFS/LibP2P Integration

This module provides a caching layer for GitHub CLI (gh) commands to reduce
API rate limit usage by caching responses locally and sharing via P2P networks.

Features:
- Local disk caching using content-addressed storage
- P2P cache sharing via libp2p (optional)
- IPFS integration for distributed caching
- Intelligent cache invalidation with TTLs
- Command-specific caching strategies

Usage:
    # In shell scripts or workflows:
    source gh_cache_wrapper.sh
    
    # In Python:
    from ipfs_kit_py.gh_cache import GHCache
    cache = GHCache()
    result = cache.run(['gh', 'repo', 'list'])
"""

import os
import sys
import json
import hashlib
import subprocess
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import local caching infrastructure
try:
    from .disk_cache_anyio import DiskCacheAnyIO
    HAS_DISK_CACHE = True
except ImportError:
    HAS_DISK_CACHE = False
    logger.warning("DiskCacheAnyIO not available - using simple file caching")

# Try to import IPFS client
try:
    from .ipfs_kit import IPFSKit
    HAS_IPFS = True
except ImportError:
    HAS_IPFS = False
    logger.debug("IPFSKit not available - IPFS caching disabled")

# Try to import LibP2P peer manager for P2P cache sharing
try:
    from .libp2p.peer_manager import Libp2pPeerManager
    from .libp2p.gossipsub_protocol import GossipSubProtocol, GossipSubMessage
    HAS_LIBP2P = True
except ImportError:
    HAS_LIBP2P = False
    logger.debug("LibP2P not available - P2P cache sharing disabled")


class GHCache:
    """
    GitHub CLI caching wrapper with IPFS and P2P support.
    
    Provides intelligent caching for gh CLI commands to reduce API calls
    and enable offline operation where possible.
    """
    
    # Cache TTLs (in seconds) for different command types
    TTL_CONFIG = {
        # Immutable data - cache indefinitely
        'immutable': {
            'patterns': ['commit', 'release view'],
            'ttl': 86400 * 365  # 1 year
        },
        # Repository metadata - medium TTL
        'repository': {
            'patterns': ['repo view', 'repo list'],
            'ttl': 3600  # 1 hour
        },
        # User data - medium TTL
        'user': {
            'patterns': ['api /user', 'auth status'],
            'ttl': 3600  # 1 hour
        },
        # Workflow runs - short TTL (frequently updated)
        'workflow': {
            'patterns': ['run list', 'run view', 'run download'],
            'ttl': 300  # 5 minutes
        },
        # PR data - short TTL
        'pr': {
            'patterns': ['pr list', 'pr view', 'pr diff', 'pr checks'],
            'ttl': 120  # 2 minutes
        },
        # Issue data - short TTL
        'issue': {
            'patterns': ['issue list', 'issue view'],
            'ttl': 120  # 2 minutes
        },
        # Default - very short TTL
        'default': {
            'patterns': [],
            'ttl': 60  # 1 minute
        }
    }
    
    # Commands that should NEVER be cached (write operations)
    NO_CACHE_COMMANDS = [
        'pr create', 'pr merge', 'pr close', 'pr comment', 'pr edit', 'pr ready',
        'issue create', 'issue comment', 'issue close', 'issue edit',
        'release create', 'release upload', 'release delete',
        'repo create', 'repo delete', 'repo fork',
        'secret set', 'secret delete',
        'variable set', 'variable delete',
        'workflow run',
    ]
    
    def __init__(self, 
                 cache_dir: Optional[str] = None,
                 enable_ipfs: bool = False,
                 enable_p2p: bool = False,
                 max_cache_size: int = 1024 * 1024 * 1024):  # 1GB default
        """
        Initialize GitHub CLI cache.
        
        Args:
            cache_dir: Directory for cache storage (default: ~/.ipfs_kit/gh_cache)
            enable_ipfs: Enable IPFS-based caching
            enable_p2p: Enable P2P cache sharing via libp2p
            max_cache_size: Maximum cache size in bytes (NOTE: not yet enforced)
        """
        self.cache_dir = Path(cache_dir or os.path.expanduser('~/.ipfs_kit/gh_cache'))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.index_file = self.cache_dir / 'index.json'
        self.index = self._load_index()
        
        self.enable_ipfs = enable_ipfs and HAS_IPFS
        self.enable_p2p = enable_p2p and HAS_LIBP2P
        self.max_cache_size = max_cache_size  # TODO: Implement cache eviction based on size
        
        # Statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'bypassed': 0,
            'errors': 0,
            'p2p_hits': 0,
            'ipfs_hits': 0,
            'local_hits': 0
        }
        
        # Initialize IPFS if available
        self.ipfs_client = None
        if self.enable_ipfs:
            try:
                self.ipfs_client = IPFSKit()
                logger.info("✅ IPFS caching enabled")
            except Exception as e:
                logger.warning(f"⚠️  Could not initialize IPFS client: {e}")
                self.enable_ipfs = False
        
        # Initialize LibP2P peer manager if available
        self.peer_manager = None
        self.gossipsub = None
        if self.enable_p2p:
            try:
                self.peer_manager = Libp2pPeerManager()
                logger.info("✅ LibP2P P2P caching enabled")
                # Note: peer_manager.start() should be called separately for async
            except Exception as e:
                logger.warning(f"⚠️  Could not initialize LibP2P peer manager: {e}")
                self.enable_p2p = False
        
        logger.info(f"📦 GitHub CLI cache initialized: {self.cache_dir}")
        logger.info(f"   IPFS: {'enabled' if self.enable_ipfs else 'disabled'}")
        logger.info(f"   P2P: {'enabled' if self.enable_p2p else 'disabled'}")
    
    def _load_index(self) -> Dict[str, Any]:
        """Load cache index from disk."""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load cache index: {e}")
                return {}
        return {}
    
    def _save_index(self):
        """Save cache index to disk."""
        try:
            with open(self.index_file, 'w') as f:
                json.dump(self.index, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save cache index: {e}")
    
    def _generate_cache_key(self, command: List[str]) -> str:
        """
        Generate cache key for a command.
        
        Args:
            command: Command and arguments list
            
        Returns:
            Cache key (hex digest)
        """
        # Include current user context for cache isolation
        user_context = os.getenv('USER', 'default')
        
        # Include GitHub host to avoid mixing caches across different hosts
        gh_host = os.getenv('GH_HOST') or os.getenv('GITHUB_SERVER_URL') or 'github.com'
        
        # Include a non-reversible hash of the GitHub token to avoid cross-account contamination
        token = os.getenv('GH_TOKEN') or os.getenv('GITHUB_TOKEN') or ''
        if token:
            token_hash = hashlib.sha256(token.encode()).hexdigest()[:16]  # First 16 chars sufficient
        else:
            token_hash = 'no-token'
        
        # Normalize command for consistent caching
        cmd_str = ' '.join(command)
        
        # Create hash from command + user context + host + token hash
        key_data = f"{user_context}:{gh_host}:{token_hash}:{cmd_str}"
        cache_key = hashlib.sha256(key_data.encode()).hexdigest()
        
        return cache_key
    
    def _get_ttl_for_command(self, command: List[str]) -> int:
        """
        Determine TTL for a command based on its type.
        
        Args:
            command: Command and arguments list
            
        Returns:
            TTL in seconds
        """
        cmd_str = ' '.join(command).lower()
        
        # Check each category
        for category, config in self.TTL_CONFIG.items():
            if category == 'default':
                continue
            for pattern in config['patterns']:
                if pattern in cmd_str:
                    return config['ttl']
        
        # Default TTL
        return self.TTL_CONFIG['default']['ttl']
    
    def _should_cache_command(self, command: List[str]) -> bool:
        """
        Determine if a command should be cached.
        
        Args:
            command: Command and arguments list
            
        Returns:
            True if command should be cached
        """
        cmd_str = ' '.join(command).lower()
        
        # Check if it's a write operation
        for no_cache_cmd in self.NO_CACHE_COMMANDS:
            if no_cache_cmd in cmd_str:
                return False
        
        # Cache all read operations
        return True
    
    def _is_cache_valid(self, cache_entry: Dict[str, Any]) -> bool:
        """
        Check if a cache entry is still valid.
        
        Args:
            cache_entry: Cache entry from index
            
        Returns:
            True if cache is valid
        """
        if 'expires_at' not in cache_entry:
            return False
        
        expires_at = datetime.fromisoformat(cache_entry['expires_at'])
        return datetime.now() < expires_at
    
    def _query_p2p_cache(self, cache_key: str) -> Optional[str]:
        """
        Query P2P peers for cached content.
        
        NOTE: P2P cache retrieval is not yet fully implemented. This is a placeholder
        that will be completed when the peer manager's cache query API is finalized.
        
        Args:
            cache_key: Cache key to search for
            
        Returns:
            Cached result from peer or None (currently always None)
        """
        if not self.enable_p2p or not self.peer_manager:
            return None
        
        try:
            logger.debug(f"P2P cache query for {cache_key[:8]} (not yet implemented)")
            
            # P2P retrieval stub - will be implemented when peer manager supports:
            # 1. Distributed cache index lookups
            # 2. DHT content provider queries  
            # 3. Peer-to-peer content requests
            # 
            # For now, P2P is limited to local caching + IPFS fallback
            
            return None
            
        except Exception as e:
            logger.debug(f"P2P cache query failed: {e}")
            return None
    
    def _get_from_ipfs(self, cache_key: str) -> Optional[str]:
        """
        Retrieve content from IPFS by CID.
        
        Args:
            cache_key: Cache key
            
        Returns:
            Content from IPFS or None
        """
        if not self.enable_ipfs or not self.ipfs_client:
            return None
        
        # Check if we have a CID for this cache key
        if cache_key not in self.index:
            return None
        
        cache_entry = self.index[cache_key]
        if 'ipfs_cid' not in cache_entry:
            return None
        
        try:
            cid = cache_entry['ipfs_cid']
            logger.debug(f"📦 Retrieving from IPFS: {cid}")
            
            # Retrieve content from IPFS
            content = self.ipfs_client.cat_str(cid)
            if content:
                self.stats['ipfs_hits'] += 1
                logger.info(f"✅ IPFS HIT: {cid}")
                return content
                
        except Exception as e:
            logger.debug(f"IPFS retrieval failed: {e}")
        
        return None
    
    def _announce_cache_entry(self, cache_key: str, ipfs_cid: Optional[str] = None):
        """
        Announce cache entry availability to P2P network.
        
        NOTE: P2P announcements are not yet implemented. This method is a placeholder
        to avoid implying that announcements are currently sent to the network.
        
        Args:
            cache_key: Cache key
            ipfs_cid: Optional IPFS CID for the content
        """
        if not self.enable_p2p or not self.peer_manager:
            return
        
        try:
            # P2P announcement mechanism (e.g., GossipSub publish) is not wired up.
            # This log is for transparency; actual network publishing must be
            # implemented in a future revision.
            logger.debug(
                f"P2P cache announcement requested for key {cache_key[:8]}, but announcement "
                "transport is not implemented yet."
            )
            
        except Exception as e:
            logger.debug(f"Cache announcement failed: {e}")
    
    def _get_from_cache(self, cache_key: str) -> Optional[str]:
        """
        Retrieve result from cache with multi-tier strategy:
        1. Local disk cache (fastest)
        2. P2P peer cache (fast, distributed)
        3. IPFS network (slower, most reliable)
        
        Args:
            cache_key: Cache key
            
        Returns:
            Cached result or None if not found/expired
        """
        # Tier 1: Local cache
        if cache_key in self.index:
            cache_entry = self.index[cache_key]
            
            # Check if cache is still valid
            if self._is_cache_valid(cache_entry):
                # Read cached data
                cache_file = self.cache_dir / cache_entry['file']
                if cache_file.exists():
                    try:
                        with open(cache_file, 'r') as f:
                            content = f.read()
                            self.stats['local_hits'] += 1
                            logger.debug(f"💾 Local cache HIT: {cache_key[:8]}...")
                            return content
                    except Exception as e:
                        logger.error(f"Could not read cache file: {e}")
            else:
                logger.debug(f"Cache expired for key: {cache_key[:8]}...")
        
        # Tier 2: P2P cache (query peers)
        if self.enable_p2p:
            p2p_result = self._query_p2p_cache(cache_key)
            if p2p_result:
                self.stats['p2p_hits'] += 1
                logger.info(f"🌐 P2P cache HIT: {cache_key[:8]}...")
                # Store locally for future use
                return p2p_result
        
        # Tier 3: IPFS network
        if self.enable_ipfs:
            ipfs_result = self._get_from_ipfs(cache_key)
            if ipfs_result:
                # Store locally for future use
                return ipfs_result
        
        return None
    
    def _store_in_cache(self, cache_key: str, command: List[str], result: str):
        """
        Store result in cache with multi-tier strategy:
        1. Store locally
        2. Store in IPFS (if enabled)
        3. Announce to P2P network (if enabled)
        
        Args:
            cache_key: Cache key
            command: Original command
            result: Command result to cache
        """
        # Determine TTL
        ttl = self._get_ttl_for_command(command)
        expires_at = datetime.now() + timedelta(seconds=ttl)
        
        # Store result in file
        cache_file = f"{cache_key}.txt"
        cache_path = self.cache_dir / cache_file
        
        ipfs_cid = None
        
        try:
            with open(cache_path, 'w') as f:
                f.write(result)
            
            # Update index
            self.index[cache_key] = {
                'command': ' '.join(command),
                'file': cache_file,
                'created_at': datetime.now().isoformat(),
                'expires_at': expires_at.isoformat(),
                'ttl': ttl,
                'size': len(result)
            }
            
            # Store in IPFS for distributed caching
            if self.enable_ipfs and self.ipfs_client:
                try:
                    ipfs_cid = self.ipfs_client.add_str(result)
                    self.index[cache_key]['ipfs_cid'] = ipfs_cid
                    logger.debug(f"📦 Stored in IPFS: {ipfs_cid}")
                except Exception as e:
                    logger.debug(f"Could not store in IPFS: {e}")
            
            self._save_index()
            
            logger.debug(f"Cached result for: {' '.join(command[:3])}... (TTL: {ttl}s)")
            
            # Announce to P2P network
            if self.enable_p2p:
                self._announce_cache_entry(cache_key, ipfs_cid)
        
        except Exception as e:
            logger.error(f"Could not store in cache: {e}")
    
    def run(self, command: List[str], use_cache: bool = True) -> Tuple[int, str, str]:
        """
        Run gh command with caching.
        
        Args:
            command: Command and arguments list (e.g., ['gh', 'repo', 'list'])
            use_cache: Whether to use cache (default: True)
            
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        # Check if this command should be cached
        should_cache = use_cache and self._should_cache_command(command)
        
        if not should_cache:
            self.stats['bypassed'] += 1
            logger.debug(f"Bypassing cache for: {' '.join(command[:3])}...")
            return self._execute_command(command)
        
        # Generate cache key
        cache_key = self._generate_cache_key(command)
        
        # Try to get from cache
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            self.stats['hits'] += 1
            logger.info(f"✅ Cache HIT: {' '.join(command[:3])}...")
            return (0, cached_result, '')
        
        # Cache miss - execute command
        self.stats['misses'] += 1
        logger.info(f"❌ Cache MISS: {' '.join(command[:3])}...")
        
        return_code, stdout, stderr = self._execute_command(command)
        
        # Store in cache if successful
        if return_code == 0 and stdout:
            self._store_in_cache(cache_key, command, stdout)
        
        return (return_code, stdout, stderr)
    
    def _execute_command(self, command: List[str]) -> Tuple[int, str, str]:
        """
        Execute a command directly.
        
        Args:
            command: Command and arguments list
            
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            return (result.returncode, result.stdout, result.stderr)
        
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {' '.join(command)}")
            self.stats['errors'] += 1
            return (1, '', 'Command timed out')
        
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            self.stats['errors'] += 1
            return (1, '', str(e))
    
    def clear_cache(self, pattern: Optional[str] = None):
        """
        Clear cache entries.
        
        Args:
            pattern: Optional pattern to match commands (clears all if None)
        """
        if pattern is None:
            # Clear all
            for cache_entry in self.index.values():
                cache_file = self.cache_dir / cache_entry['file']
                cache_file.unlink(missing_ok=True)
            self.index = {}
            self._save_index()
            logger.info("🗑️  Cleared all cache entries")
        else:
            # Clear matching entries
            to_remove = []
            for key, entry in self.index.items():
                if pattern in entry['command']:
                    cache_file = self.cache_dir / entry['file']
                    cache_file.unlink(missing_ok=True)
                    to_remove.append(key)
            
            for key in to_remove:
                del self.index[key]
            
            self._save_index()
            logger.info(f"🗑️  Cleared {len(to_remove)} cache entries matching: {pattern}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics including P2P and IPFS metrics.
        
        Returns:
            Dictionary of cache statistics
        """
        total_requests = self.stats['hits'] + self.stats['misses'] + self.stats['bypassed']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        # Calculate local, P2P, and IPFS hit rates
        local_rate = (self.stats['local_hits'] / total_requests * 100) if total_requests > 0 else 0
        p2p_rate = (self.stats['p2p_hits'] / total_requests * 100) if total_requests > 0 else 0
        ipfs_rate = (self.stats['ipfs_hits'] / total_requests * 100) if total_requests > 0 else 0
        
        # Calculate cache size
        total_size = sum(entry.get('size', 0) for entry in self.index.values())
        
        # Count IPFS-backed entries
        ipfs_entries = sum(1 for entry in self.index.values() if 'ipfs_cid' in entry)
        
        return {
            **self.stats,
            'total_requests': total_requests,
            'hit_rate': f"{hit_rate:.1f}%",
            'local_hit_rate': f"{local_rate:.1f}%",
            'p2p_hit_rate': f"{p2p_rate:.1f}%",
            'ipfs_hit_rate': f"{ipfs_rate:.1f}%",
            'cache_entries': len(self.index),
            'ipfs_backed_entries': ipfs_entries,
            'cache_size_mb': total_size / (1024 * 1024),
            'cache_dir': str(self.cache_dir),
            'ipfs_enabled': self.enable_ipfs,
            'p2p_enabled': self.enable_p2p
        }
    
    def print_stats(self):
        """Print cache statistics to console including P2P and IPFS metrics."""
        stats = self.get_stats()
        print("\n📊 GitHub CLI Cache Statistics:")
        print(f"   Total Requests: {stats['total_requests']}")
        print(f"   Cache Hits: {stats['hits']} ({stats['hit_rate']})")
        print(f"     └─ Local: {stats['local_hits']} ({stats['local_hit_rate']})")
        print(f"     └─ P2P: {stats['p2p_hits']} ({stats['p2p_hit_rate']})")
        print(f"     └─ IPFS: {stats['ipfs_hits']} ({stats['ipfs_hit_rate']})")
        print(f"   Cache Misses: {stats['misses']}")
        print(f"   Bypassed: {stats['bypassed']}")
        print(f"   Errors: {stats['errors']}")
        print(f"   Cache Entries: {stats['cache_entries']}")
        if stats['ipfs_enabled']:
            print(f"   IPFS-Backed Entries: {stats['ipfs_backed_entries']}")
        print(f"   Cache Size: {stats['cache_size_mb']:.2f} MB")
        print(f"   Cache Dir: {stats['cache_dir']}")
        print(f"   IPFS: {'✅ Enabled' if stats['ipfs_enabled'] else '❌ Disabled'}")
        print(f"   P2P: {'✅ Enabled' if stats['p2p_enabled'] else '❌ Disabled'}\n")


def main():
    """CLI entry point for gh_cache."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='GitHub CLI caching wrapper with IPFS/P2P support'
    )
    parser.add_argument('command', nargs='+', help='gh command to run')
    parser.add_argument('--no-cache', action='store_true', help='Bypass cache')
    parser.add_argument('--clear-cache', action='store_true', help='Clear cache before running')
    parser.add_argument('--stats', action='store_true', help='Show cache statistics')
    parser.add_argument('--cache-dir', help='Cache directory')
    parser.add_argument('--enable-ipfs', action='store_true', help='Enable IPFS caching')
    parser.add_argument('--enable-p2p', action='store_true', help='Enable P2P cache sharing via libp2p')
    
    args = parser.parse_args()
    
    # Initialize cache
    cache = GHCache(
        cache_dir=args.cache_dir,
        enable_ipfs=args.enable_ipfs,
        enable_p2p=args.enable_p2p
    )
    
    # Clear cache if requested
    if args.clear_cache:
        cache.clear_cache()
    
    # Run command
    if not args.stats:
        return_code, stdout, stderr = cache.run(args.command, use_cache=not args.no_cache)
        
        # Print output
        if stdout:
            print(stdout, end='')
        if stderr:
            print(stderr, end='', file=sys.stderr)
        
        sys.exit(return_code)
    
    # Show stats
    cache.print_stats()


if __name__ == '__main__':
    main()

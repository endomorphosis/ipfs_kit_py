"""
Cache modules for IPFS Kit to improve performance and reduce redundant operations.

This package provides various caching mechanisms designed for different use cases:

1. Semantic Cache: For caching semantically similar search queries and results
2. Tiered Cache: For efficiently managing content across memory and disk
3. Content Cache: For caching IPFS content with CID-based retrieval

These caching mechanisms can significantly improve performance, especially
for repeated operations or operations with similar parameters.
"""

from .semantic_cache import CacheEntry, QueryVector, SemanticCache

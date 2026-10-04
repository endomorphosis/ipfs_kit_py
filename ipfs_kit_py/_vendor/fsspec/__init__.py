"""Minimal fsspec compatibility layer.

The upstream `fsspec` package is an optional dependency for this repo.
Some test environments (and certain zero-touch install targets) don't have it
available, but parts of `ipfs_kit_py` still import `fsspec` symbols.

This module implements the small subset of the public API that `ipfs_kit_py`
needs for import-time class definitions and basic registry usage.

It is NOT intended to be a complete replacement for `fsspec`.
"""

from __future__ import annotations

from .registry import filesystem, register_implementation, get_filesystem_class

__all__ = [
    "filesystem",
    "register_implementation",
    "get_filesystem_class",
]

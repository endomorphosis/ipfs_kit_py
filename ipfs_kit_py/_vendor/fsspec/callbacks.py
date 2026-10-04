"""Callback stubs used by `ipfs_kit_py`.

Upstream `fsspec.callbacks.DEFAULT_CALLBACK` is used as a sentinel.
"""

from __future__ import annotations


class _DefaultCallback:
    def __call__(self, *args, **kwargs):
        return None


DEFAULT_CALLBACK = _DefaultCallback()

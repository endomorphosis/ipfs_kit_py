"""Compatibility import for the canonical Iroh bucket-tiering module."""

from .iroh.bucket_tiering import *  # noqa: F403
from .iroh.bucket_tiering import __all__ as _bucket_tiering_all

__all__ = _bucket_tiering_all

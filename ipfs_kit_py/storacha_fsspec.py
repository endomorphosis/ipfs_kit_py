"""Storacha fsspec registration and filesystem export."""

from .enhanced_fsspec import StorachaFileSystem, register_fsspec_implementations


register_fsspec_implementations(clobber=True)


__all__ = ["StorachaFileSystem", "register_fsspec_implementations"]

"""Tiny subset of `fsspec.spec`.

Only provides the base classes referenced by `ipfs_kit_py.ipfs_fsspec`.
"""

from __future__ import annotations

from typing import Any, Optional


class AbstractFileSystem:
    """Minimal stand-in for `fsspec.spec.AbstractFileSystem`."""

    protocol: str | tuple[str, ...] = ("file",)

    def __init__(self, **storage_options: Any):
        self.storage_options = dict(storage_options)

    def open(self, path: str, mode: str = "rb", **kwargs: Any):
        raise NotImplementedError("AbstractFileSystem.open")


class AbstractBufferedFile:
    """Minimal stand-in for `fsspec.spec.AbstractBufferedFile`."""

    def __init__(
        self,
        fs: AbstractFileSystem,
        path: str,
        mode: str = "rb",
        block_size: Optional[int] = None,
        autocommit: bool = True,
        cache_type: str = "readahead",
        **kwargs: Any,
    ):
        self.fs = fs
        self.path = path
        self.mode = mode
        self.block_size = block_size
        self.autocommit = autocommit
        self.cache_type = cache_type
        self.kwargs = dict(kwargs)
        self.closed = False

    def close(self) -> None:
        self.closed = True

    def readable(self) -> bool:
        return "r" in self.mode or "+" in self.mode

    def writable(self) -> bool:
        return any(ch in self.mode for ch in ("w", "a", "+"))

    def read(self, size: int = -1) -> bytes:
        raise NotImplementedError("AbstractBufferedFile.read")

    def write(self, data: bytes) -> int:
        raise NotImplementedError("AbstractBufferedFile.write")

"""Minimal enhanced VFS API stubs for columnar IPLD tests."""

from __future__ import annotations

from typing import Any, Optional


class VFSMetadataAPI:
    """Stub VFS metadata API."""

    def __init__(
        self,
        parquet_bridge: Optional[Any] = None,
        car_bridge: Optional[Any] = None,
        cache_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        self.parquet_bridge = parquet_bridge
        self.car_bridge = car_bridge
        self.cache_manager = cache_manager
        self.options = kwargs


class VectorIndexAPI:
    """Stub vector index API."""

    def __init__(self, **kwargs: Any) -> None:
        self.options = kwargs


class KnowledgeGraphAPI:
    """Stub knowledge graph API."""

    def __init__(self, **kwargs: Any) -> None:
        self.options = kwargs


class PinsetAPI:
    """Stub pinset API."""

    def __init__(self, **kwargs: Any) -> None:
        self.options = kwargs

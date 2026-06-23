"""Compatibility wrappers for the standalone :mod:`walrus_fsspec` package.

The canonical Walrus HTTP client and response normalization logic now lives in
``walrus_fsspec``. This module preserves the historical ``ipfs_kit_py`` import
surface, environment variable aliases, and default cache location.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping, Optional

from walrus_fsspec.storage import (  # noqa: F401
    WalrusBlobInfo,
    WalrusConfigurationError,
    WalrusStorageClient as _BaseWalrusStorageClient,
)
from walrus_fsspec.storage import WalrusMetadataIndex as _BaseWalrusMetadataIndex

WALRUS_INDEX_SCHEMA = "ipfs_kit_py.walrus.index.v1"


class WalrusMetadataIndex(_BaseWalrusMetadataIndex):
    """ipfs_kit_py-compatible default location for the Walrus metadata index."""

    @staticmethod
    def default_path() -> Path:
        return Path.home() / ".cache" / "ipfs_kit_py" / "walrus" / "index.json"

    @staticmethod
    def _empty_index() -> dict[str, Any]:
        return {"schema": WALRUS_INDEX_SCHEMA, "items": {}}

    def load(self) -> dict[str, Any]:
        payload = super().load()
        return {"schema": payload.get("schema") or WALRUS_INDEX_SCHEMA, "items": payload["items"]}

    def _write(self, index: Mapping[str, Any]) -> None:
        super()._write({"schema": index.get("schema") or WALRUS_INDEX_SCHEMA, "items": index.get("items")})


class WalrusStorageClient(_BaseWalrusStorageClient):
    """Walrus client backed by ``walrus_fsspec`` with ipfs_kit_py aliases.

    The standalone package owns the behavior. This subclass only resolves legacy
    ``ABBY_RUNTIME_*`` and ``VITE_WALRUS_STORAGE_*`` environment variables and
    keeps the previous default index path under ``~/.cache/ipfs_kit_py``.
    """

    def __init__(
        self,
        publisher_url: Optional[str] = None,
        aggregator_url: Optional[str] = None,
        delete_url: Optional[str] = None,
        client_token: Optional[str] = None,
        epochs: Optional[int] = None,
        deletable: Optional[bool] = None,
        timeout: float = 30.0,
        headers: Optional[Mapping[str, str]] = None,
        transport: Any = None,
        index_path: Optional[os.PathLike[str] | str] = None,
    ) -> None:
        resolved_index_path = index_path or self._env_first(
            "WALRUS_INDEX_PATH",
            "ABBY_RUNTIME_WALRUS_INDEX_PATH",
            "VITE_WALRUS_STORAGE_INDEX_PATH",
        )
        super().__init__(
            publisher_url=publisher_url
            or self._env_first(
                "WALRUS_PUBLISHER_URL",
                "ABBY_RUNTIME_WALRUS_PUBLISHER_URL",
                "VITE_WALRUS_STORAGE_PUBLISHER_URL",
            ),
            aggregator_url=aggregator_url
            or self._env_first(
                "WALRUS_AGGREGATOR_URL",
                "ABBY_RUNTIME_WALRUS_AGGREGATOR_URL",
                "VITE_WALRUS_STORAGE_AGGREGATOR_URL",
            ),
            delete_url=delete_url
            or self._env_first(
                "WALRUS_DELETE_URL",
                "ABBY_RUNTIME_WALRUS_DELETE_URL",
                "VITE_WALRUS_STORAGE_DELETE_URL",
            ),
            client_token=client_token
            or self._env_first(
                "WALRUS_CLIENT_TOKEN",
                "ABBY_RUNTIME_WALRUS_CLIENT_TOKEN",
                "VITE_WALRUS_STORAGE_CLIENT_TOKEN",
            ),
            epochs=epochs
            if epochs is not None
            else self._int_or_none(
                self._env_first(
                    "WALRUS_EPOCHS",
                    "ABBY_RUNTIME_WALRUS_EPOCHS",
                    "VITE_WALRUS_STORAGE_EPOCHS",
                )
            ),
            deletable=deletable
            if deletable is not None
            else self._bool_or_none(
                self._env_first(
                    "WALRUS_DELETABLE",
                    "ABBY_RUNTIME_WALRUS_DELETABLE",
                    "VITE_WALRUS_STORAGE_DELETABLE",
                )
            ),
            timeout=timeout,
            headers=headers,
            transport=transport,
            index_path=resolved_index_path,
        )
        self.index = WalrusMetadataIndex(resolved_index_path)


__all__ = [
    "WALRUS_INDEX_SCHEMA",
    "WalrusBlobInfo",
    "WalrusConfigurationError",
    "WalrusMetadataIndex",
    "WalrusStorageClient",
]

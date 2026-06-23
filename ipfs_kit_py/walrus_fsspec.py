"""Compatibility fsspec backend for Walrus blob storage.

``walrus_fsspec`` is the canonical backend. This module keeps the historical
``ipfs_kit_py.walrus_fsspec`` import path and uses the compatibility storage
client from :mod:`ipfs_kit_py.walrus_storage` for legacy environment aliases.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Mapping, Optional

import httpx

try:
    import fsspec
    from fsspec.asyn import mirror_sync_methods
    from walrus_fsspec import WalrusFileSystem as _BaseWalrusFileSystem

    HAVE_FSSPEC = True
except Exception:  # pragma: no cover - exercised only without optional deps
    fsspec = None  # type: ignore[assignment]
    mirror_sync_methods = None  # type: ignore[assignment]
    _BaseWalrusFileSystem = object  # type: ignore[assignment,misc]
    HAVE_FSSPEC = False

from .walrus_storage import WalrusStorageClient

logger = logging.getLogger(__name__)


class WalrusFileSystem(_BaseWalrusFileSystem):
    """ipfs_kit_py-compatible subclass of the standalone Walrus fsspec backend."""

    def __init__(
        self,
        *,
        client: Optional[WalrusStorageClient] = None,
        publisher_url: Optional[str] = None,
        aggregator_url: Optional[str] = None,
        delete_url: Optional[str] = None,
        client_token: Optional[str] = None,
        epochs: Optional[int] = None,
        deletable: Optional[bool] = None,
        timeout: float = 30.0,
        headers: Optional[Mapping[str, str]] = None,
        transport: Optional[httpx.BaseTransport] = None,
        index_path: Optional[os.PathLike[str] | str] = None,
        **kwargs: Any,
    ) -> None:
        if not HAVE_FSSPEC:
            raise ImportError("fsspec and walrus-fsspec are required to use WalrusFileSystem")
        super().__init__(
            client=client
            or WalrusStorageClient(
                publisher_url=publisher_url,
                aggregator_url=aggregator_url,
                delete_url=delete_url,
                client_token=client_token,
                epochs=epochs,
                deletable=deletable,
                timeout=timeout,
                headers=headers,
                transport=transport,
                index_path=index_path,
            ),
            **kwargs,
        )


if HAVE_FSSPEC:  # pragma: no branch
    mirror_sync_methods(WalrusFileSystem)
    try:
        fsspec.register_implementation("walrus", WalrusFileSystem, clobber=True)
    except Exception:  # pragma: no cover - defensive registration guard
        logger.debug("Walrus fsspec registration skipped", exc_info=True)


__all__ = ["HAVE_FSSPEC", "WalrusFileSystem"]

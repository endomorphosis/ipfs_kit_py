"""AnyIO facade over the single synchronized legacy ARC adapter."""

from __future__ import annotations

import asyncio
from functools import partial
from typing import Any, Callable, TypeVar

from ipfs_kit_py.arc_cache import ARCache


T = TypeVar("T")


class ARCacheAnyIO:
    """Async calls delegated to one ``ARCache`` instance; no copied ARC state."""

    def __init__(self, *args: Any, cache: ARCache | None = None, **kwargs: Any) -> None:
        self.cache = cache if cache is not None else ARCache(*args, **kwargs)

    async def _run(self, function: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        call = partial(function, *args, **kwargs)
        try:
            import anyio
        except ImportError:
            return await asyncio.to_thread(call)
        return await anyio.to_thread.run_sync(call)

    async def async_contains(self, key: str) -> bool:
        return await self._run(self.cache.contains, key)

    async def async_get(self, key: str, default: bytes | None = None) -> bytes | None:
        return await self._run(self.cache.get, key, default)

    async def async_put(self, key: str, value: bytes) -> bool:
        return await self._run(self.cache.put, key, value)

    async def async_delete(self, key: str) -> bool:
        return await self._run(self.cache.delete, key)

    async def async_evict(self, key: str) -> bool:
        return await self._run(self.cache.evict, key)

    async def async_clear(self) -> None:
        await self._run(self.cache.clear)

    async def async_get_stats(self) -> dict[str, Any]:
        return await self._run(self.cache.get_stats)

    get_async = async_get
    put_async = async_put
    set_async = async_put
    contains_async = async_contains
    delete_async = async_delete
    evict_async = async_evict
    clear_async = async_clear
    get_stats_async = async_get_stats
    async_set = async_put

    def __getattr__(self, name: str) -> Any:
        return getattr(self.cache, name)


AnyIOARCache = ARCacheAnyIO

__all__ = ["ARCacheAnyIO", "AnyIOARCache"]

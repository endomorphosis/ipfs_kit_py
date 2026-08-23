"""Tenant-safe execution cache profiles (EAAEF-053)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final

CACHE_SCHEMA: Final[str] = "ipfs_kit_py/execution-cache-profile@1"


class CacheProfileError(ValueError):
    """Cache profile is not tenant-safe."""


@dataclass(frozen=True)
class ExecutionCacheProfile:
    lock_id: str
    toolchain_id: str
    architecture: str
    environment_id: str
    network_policy: str
    writable_shared: bool = False

    def __post_init__(self) -> None:
        for name in ("lock_id", "toolchain_id", "architecture", "environment_id", "network_policy"):
            if not str(getattr(self, name) or "").strip():
                raise CacheProfileError(f"{name} is required")
        if self.writable_shared:
            raise CacheProfileError("untrusted writable cache cannot be shared across tenants")
        if self.network_policy not in {"deny", "allowlist"}:
            raise CacheProfileError("network_policy must be deny or allowlist")

    @property
    def cache_key(self) -> tuple[str, ...]:
        return (
            self.lock_id,
            self.toolchain_id,
            self.architecture,
            self.environment_id,
            self.network_policy,
        )

    def to_dict(self) -> Mapping[str, Any]:
        return MappingProxyType(
            {
                "schema": CACHE_SCHEMA,
                "lock_id": self.lock_id,
                "toolchain_id": self.toolchain_id,
                "architecture": self.architecture,
                "environment_id": self.environment_id,
                "network_policy": self.network_policy,
                "writable_shared": False,
                "cache_key": list(self.cache_key),
            }
        )

"""EAAEF-053: cache keys isolate tenants."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

KIT_ROOT = Path(__file__).resolve().parents[1]
if str(KIT_ROOT) not in sys.path:
    sys.path.insert(0, str(KIT_ROOT))

from execution_cache.profile import CacheProfileError, ExecutionCacheProfile


def test_key_includes_lock_toolchain_arch_env_network() -> None:
    profile = ExecutionCacheProfile(
        lock_id="lock-1",
        toolchain_id="py312",
        architecture="x86_64",
        environment_id="hermetic",
        network_policy="deny",
    )
    assert profile.cache_key == ("lock-1", "py312", "x86_64", "hermetic", "deny")
    other = ExecutionCacheProfile(
        lock_id="lock-2",
        toolchain_id="py312",
        architecture="x86_64",
        environment_id="hermetic",
        network_policy="deny",
    )
    assert profile.cache_key != other.cache_key


def test_shared_writable_cache_is_rejected() -> None:
    with pytest.raises(CacheProfileError, match="shared"):
        ExecutionCacheProfile(
            lock_id="lock-1",
            toolchain_id="py312",
            architecture="x86_64",
            environment_id="hermetic",
            network_policy="deny",
            writable_shared=True,
        )

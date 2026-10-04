"""Compatibility package for tests.

The upstream codebase primarily exposes MCP components under the
`ipfs_kit_py.mcp` package. Some tests (and older integrations) import from a
top-level `mcp` package.

This package provides lightweight shims to keep those imports working without
forcing heavy daemon startup during test runs.
"""

import importlib
from types import ModuleType
from typing import Any


__all__ = [
    "bucket_vfs_mcp_tools",
    "controllers",
    "dashboard",
    "enhanced_mcp_server_with_daemon_mgmt",
    "enhanced_mcp_server_with_vfs",
    "enhanced_vfs_mcp_server",
    "standalone_vfs_mcp_server",
    "vfs_version_mcp_tools",
]


def __getattr__(name: str) -> Any:
    if name in __all__:
        return importlib.import_module(f"{__name__}.{name}")
    raise AttributeError(name)


def __dir__() -> list[str]:
    return sorted(set(globals().keys()) | set(__all__))

"""Lazy public facade for the optional MCP server integration."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from ipfs_kit_py import OptionalDependencyError

_LAZY_EXPORTS = {
    "HierarchicalToolManager": (".hierarchical_tool_manager", "HierarchicalToolManager"),
    "TOOL_GROUPS": (".tools", "TOOL_GROUPS"),
}


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute = _LAZY_EXPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    try:
        value = getattr(import_module(module_name, __name__), attribute)
    except ModuleNotFoundError as exc:
        raise OptionalDependencyError(name, extra="mcp", dependency=exc.name) from exc
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY_EXPORTS))


__all__ = ["HierarchicalToolManager", "TOOL_GROUPS"]

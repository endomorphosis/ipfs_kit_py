"""Minimal fsspec registry implementation.

Supports `register_implementation` and `filesystem` used by `ipfs_kit_py`.
"""

from __future__ import annotations

from typing import Any, Dict, Type

from .spec import AbstractFileSystem

_REGISTRY: Dict[str, Type[AbstractFileSystem]] = {}


def register_implementation(
    protocol: str,
    cls: Type[AbstractFileSystem],
    clobber: bool = False,
    errtxt: str | None = None,
) -> None:
    """Register a filesystem class using upstream fsspec's core semantics."""

    del errtxt  # Lazy import error text is inapplicable to this class-only registry.
    name = str(protocol)
    existing = _REGISTRY.get(name)
    if existing is not None and existing is not cls and not clobber:
        raise ValueError(f"Name ({name}) is already registered and clobber is False")
    _REGISTRY[name] = cls


def get_filesystem_class(protocol: str) -> Type[AbstractFileSystem]:
    protocol = str(protocol)
    if protocol not in _REGISTRY:
        raise KeyError(f"No filesystem registered for protocol: {protocol}")
    return _REGISTRY[protocol]


def filesystem(protocol: str, **storage_options: Any) -> AbstractFileSystem:
    fs_cls = get_filesystem_class(protocol)
    # Shared multi-protocol implementations need to know which registry key
    # selected them.  Upstream fsspec conveys this through URL-derived kwargs;
    # preserve the same convention in the compatibility factory.
    if str(protocol) in {"iroh", "iroh+blob"}:
        storage_options.setdefault("_iroh_protocol", str(protocol))
    return fs_cls(**storage_options)

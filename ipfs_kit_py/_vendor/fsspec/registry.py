"""Minimal fsspec registry implementation.

Supports `register_implementation` and `filesystem` used by `ipfs_kit_py`.
"""

from __future__ import annotations

from typing import Any, Dict, Type

from .spec import AbstractFileSystem


_REGISTRY: Dict[str, Type[AbstractFileSystem]] = {}


def register_implementation(protocol: str, cls: Type[AbstractFileSystem]) -> None:
    _REGISTRY[str(protocol)] = cls


def get_filesystem_class(protocol: str) -> Type[AbstractFileSystem]:
    protocol = str(protocol)
    if protocol not in _REGISTRY:
        raise KeyError(f"No filesystem registered for protocol: {protocol}")
    return _REGISTRY[protocol]


def filesystem(protocol: str, **storage_options: Any) -> AbstractFileSystem:
    fs_cls = get_filesystem_class(protocol)
    return fs_cls(**storage_options)

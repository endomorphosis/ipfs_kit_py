"""Lazy, local capability facts for test-reuse integrations.

These facts answer only whether explicitly named executables are present.  They
do not install binaries, initialise repositories, start daemons, or connect to
any transport.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Callable, Mapping

__test__ = False


@dataclass(frozen=True)
class ReuseCapability:
    name: str
    available: bool
    detail: str


class TestReuseCapabilities:
    """A lazy probe collection; construction has no observable probing."""

    __test__ = False
    authoritative = False

    def __init__(self, *, which: Callable[[str], str | None] = shutil.which, names: tuple[str, ...] = ("ipfs", "lotus", "iroh")):
        self._which = which
        self._names = names
        self._cache: dict[str, ReuseCapability] = {}

    def probe(self, name: str) -> ReuseCapability:
        if name not in self._names:
            return ReuseCapability(name, False, "unsupported capability")
        if name not in self._cache:
            executable = self._which(name)
            self._cache[name] = ReuseCapability(
                name, executable is not None,
                executable if executable is not None else "executable not found",
            )
        return self._cache[name]

    def snapshot(self) -> Mapping[str, ReuseCapability]:
        return {name: self.probe(name) for name in self._names}

    def can_authorize_proof(self) -> bool:
        """Capability detection is never proof validation."""
        return False


KitTestReuseCapabilities = TestReuseCapabilities

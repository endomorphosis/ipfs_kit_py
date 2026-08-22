"""Bounded trust-aware ContextPacks (EAAEF-063)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final


PACK_SCHEMA: Final[str] = "ipfs_kit_py/context-pack/external-agent@1"
KINDS: Final[frozenset[str]] = frozenset(
    {
        "edit_critical_raw_source",
        "verified_capsule",
        "conservative_capsule",
        "heuristic_capsule",
        "conversation",
        "legal",
        "proof",
        "counterexample",
        "assumption",
    }
)


class ContextPackError(ValueError):
    """ContextPack mix is unsafe."""


@dataclass(frozen=True)
class ContextItem:
    kind: str
    identity: str
    opaque_critical: bool = False

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ContextPackError(f"unknown context kind: {self.kind}")
        if not str(self.identity).strip():
            raise ContextPackError("identity is required")
        if self.opaque_critical and self.kind == "heuristic_capsule":
            raise ContextPackError("heuristic capsules cannot replace opaque critical code")

    def to_dict(self) -> Mapping[str, Any]:
        return MappingProxyType(
            {
                "schema": PACK_SCHEMA,
                "kind": self.kind,
                "identity": self.identity,
                "opaque_critical": bool(self.opaque_critical),
            }
        )


def pack(items: Sequence[ContextItem | Mapping[str, Any]]) -> tuple[ContextItem, ...]:
    compiled = []
    for item in items:
        if isinstance(item, ContextItem):
            compiled.append(item)
        else:
            compiled.append(
                ContextItem(
                    kind=str(item.get("kind") or ""),
                    identity=str(item.get("identity") or ""),
                    opaque_critical=bool(item.get("opaque_critical")),
                )
            )
    return tuple(compiled)

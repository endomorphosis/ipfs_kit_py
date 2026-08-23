"""Bounded trust-aware ContextPacks (EAAEF-063)."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final

PACK_SCHEMA: Final[str] = "ipfs_kit_py/context-pack/external-agent@1"
DEFAULT_MAX_ITEMS: Final[int] = 256
ABSOLUTE_MAX_ITEMS: Final[int] = 1_024
_IDENTITY_RE: Final[re.Pattern[str]] = re.compile(
    r"^(sha256:[0-9a-f]{64}|b[a-z2-7]{20,})$"
)
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
        kind = str(self.kind or "").strip().lower()
        if kind not in KINDS:
            raise ContextPackError(f"unknown context kind: {kind}")
        object.__setattr__(self, "kind", kind)
        identity = str(self.identity or "").strip().lower()
        if not _IDENTITY_RE.fullmatch(identity):
            raise ContextPackError("identity must be a SHA-256 or CIDv1 identity")
        object.__setattr__(self, "identity", identity)
        if self.opaque_critical and kind == "heuristic_capsule":
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


def pack(
    items: Sequence[ContextItem | Mapping[str, Any]],
    *,
    max_items: int = DEFAULT_MAX_ITEMS,
) -> tuple[ContextItem, ...]:
    if (
        isinstance(max_items, bool)
        or not isinstance(max_items, int)
        or max_items < 1
        or max_items > ABSOLUTE_MAX_ITEMS
    ):
        raise ContextPackError("max_items is outside the admitted bound")
    if isinstance(items, (str, bytes, bytearray)) or not isinstance(items, Sequence):
        raise ContextPackError("items must be a bounded sequence")
    if len(items) > max_items:
        raise ContextPackError("ContextPack exceeds max_items")
    compiled: list[ContextItem] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        if isinstance(item, ContextItem):
            compiled_item = item
        elif isinstance(item, Mapping):
            compiled_item = ContextItem(
                kind=str(item.get("kind") or ""),
                identity=str(item.get("identity") or ""),
                opaque_critical=bool(item.get("opaque_critical")),
            )
        else:
            raise ContextPackError("ContextPack items must be objects")
        key = (compiled_item.kind, compiled_item.identity)
        if key in seen:
            raise ContextPackError("ContextPack must not contain duplicate identities")
        seen.add(key)
        compiled.append(compiled_item)
    return tuple(compiled)

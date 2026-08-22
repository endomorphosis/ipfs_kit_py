"""EAAEF-063: heuristics cannot replace opaque critical source."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

KIT_ROOT = Path(__file__).resolve().parents[1]
if str(KIT_ROOT) not in sys.path:
    sys.path.insert(0, str(KIT_ROOT))

from context_pack.external_agent import ContextPackError, pack


def test_pack_distinguishes_kinds() -> None:
    items = pack(
        (
            {"kind": "edit_critical_raw_source", "identity": "sha256:" + "a" * 64, "opaque_critical": True},
            {"kind": "verified_capsule", "identity": "sha256:" + "b" * 64},
        )
    )
    assert items[0].opaque_critical is True
    with pytest.raises(ContextPackError, match="heuristic"):
        pack(({"kind": "heuristic_capsule", "identity": "sha256:" + "c" * 64, "opaque_critical": True},))

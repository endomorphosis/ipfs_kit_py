"""Compact fixture recipes expanded into RuntimeReadinessFixture records.

Recipes intentionally omit full schema envelopes and content IDs; expand.py
materializes FaultSchedule@1 / ExpectedStateTrace@1 / RuntimeReadinessFixture@1
with deterministic content identifiers.
"""

from __future__ import annotations

from typing import Any, Final, Mapping, Sequence

from .catalog import CONFIRMED_BLOCKERS
from ._recipe_data import RECIPE_RECORDS

Recipe = dict[str, Any]

_RECIPE_LIST: Final[tuple[Recipe, ...]] = tuple(
    dict(record) for record in RECIPE_RECORDS
)

RECIPE_CATALOG: Final[dict[str, Recipe]] = {
    str(recipe["slug"]): recipe for recipe in _RECIPE_LIST
}


def all_recipes() -> tuple[Recipe, ...]:
    """Return recipes in stable catalog order."""
    return _RECIPE_LIST


def covered_blockers() -> frozenset[str]:
    found: set[str] = set()
    for recipe in _RECIPE_LIST:
        found.update(str(b) for b in recipe.get("blocker_refs", ()))
    return frozenset(found)


def assert_blockers_covered() -> None:
    missing = set(CONFIRMED_BLOCKERS) - covered_blockers()
    if missing:
        raise AssertionError(
            f"recipes missing confirmed blockers: {', '.join(sorted(missing))}"
        )

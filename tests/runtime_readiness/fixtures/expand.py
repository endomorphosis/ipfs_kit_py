"""Expand compact recipes into content-identified fixture records and manifests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Final, Mapping, Sequence

from .catalog import (
    CONFIRMED_BLOCKERS,
    REQUIRED_COVERAGE_CATEGORIES,
    REQUIRED_UCAN_VARIANTS,
)
from .recipes import all_recipes
from .schema import (
    EXPECTED_STATE_TRACE_SCHEMA,
    FAULT_SCHEDULE_SCHEMA,
    FIXTURE_MANIFEST_SCHEMA,
    RUNTIME_READINESS_FIXTURE_SCHEMA,
    FixtureValidationError,
    validate_fixture,
    validate_manifest,
)

MANIFEST_ID: Final[str] = "manifest:runtime-readiness-fixtures@1"
INTERFACE_BUNDLE: Final[str] = (
    "RuntimeReadinessFixture@1+FaultSchedule@1+ExpectedStateTrace@1"
)


def canonical_json(value: Any) -> str:
    """Deterministic JSON for content addressing (sorted keys, no whitespace)."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def content_id_for(value: Any) -> str:
    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _with_content_id(body: dict[str, Any]) -> dict[str, Any]:
    """Attach sha256 content_id over the body without the content_id field."""
    out = dict(body)
    out["content_id"] = content_id_for(out)
    return out


def _expand_fault_schedule(
    slug: str, faults: Sequence[Mapping[str, Any]]
) -> dict[str, Any] | None:
    if not faults:
        return None
    body_faults: list[dict[str, Any]] = []
    for fault in faults:
        core = {
            "kind": fault["kind"],
            "at_operation_index": fault["at_operation_index"],
            "effects": list(fault.get("effects", ())),
            "parameters": dict(fault.get("parameters", {})),
        }
        body_faults.append(_with_content_id(core))
    schedule_body = {
        "schema": FAULT_SCHEDULE_SCHEMA,
        "schedule_id": f"fault-schedule:{slug}@1",
        "faults": body_faults,
        "finite": True,
        "safe": True,
    }
    return _with_content_id(schedule_body)


def _expand_trace(slug: str, recipe: Mapping[str, Any]) -> dict[str, Any]:
    steps_out: list[dict[str, Any]] = []
    for step in recipe.get("steps", ()):
        core = {
            "index": step["index"],
            "state": step["state"],
            "operation": step.get("operation"),
            "error_code": step.get("error_code"),
            "observed_effect": step.get("observed_effect", "none"),
            "state_snapshot": dict(step.get("state_snapshot") or {}),
        }
        steps_out.append(_with_content_id(core))
    terminal = recipe.get("terminal") or {}
    trace_body = {
        "schema": EXPECTED_STATE_TRACE_SCHEMA,
        "trace_id": f"trace:{slug}@1",
        "steps": steps_out,
        "terminal": {
            "outcome": terminal["outcome"],
            "namespace": dict(terminal.get("namespace") or {}),
            "evidence": dict(terminal.get("evidence") or {}),
            "error_code": terminal.get("error_code"),
        },
        "finite": True,
        "safe": True,
    }
    return _with_content_id(trace_body)


def expand_recipe(recipe: Mapping[str, Any]) -> dict[str, Any]:
    """Expand one recipe into a RuntimeReadinessFixture@1 record."""
    slug = str(recipe["slug"])
    fault_schedule = _expand_fault_schedule(slug, recipe.get("faults") or ())
    expected_trace = _expand_trace(slug, recipe)
    body = {
        "schema": RUNTIME_READINESS_FIXTURE_SCHEMA,
        "fixture_id": f"fixture:{slug}@1",
        "subsystem": recipe["subsystem"],
        "polarity": recipe["polarity"],
        "categories": list(recipe["categories"]),
        "blocker_refs": list(recipe.get("blocker_refs") or ()),
        "description": recipe["description"],
        "initial_state": dict(recipe.get("initial_state") or {}),
        "operations": [dict(op) for op in recipe["operations"]],
        "fault_schedule": fault_schedule,
        "expected_trace": expected_trace,
        "safety": {
            "network": False,
            "credentials": False,
            "user_paths": False,
            "executable_payloads": False,
            "production_side_effects": False,
        },
        "hermetic": True,
        "finite": True,
    }
    fixture = _with_content_id(body)
    validate_fixture(fixture)
    return fixture


def expand_all_recipes(
    recipes: Sequence[Mapping[str, Any]] | None = None,
) -> tuple[dict[str, Any], ...]:
    source = recipes if recipes is not None else all_recipes()
    fixtures = tuple(expand_recipe(recipe) for recipe in source)
    return tuple(sorted(fixtures, key=lambda f: str(f["fixture_id"])))


def fixture_content_id(fixture: Mapping[str, Any]) -> str:
    cid = fixture.get("content_id")
    if not isinstance(cid, str) or not cid.startswith("sha256:"):
        raise FixtureValidationError(
            "fixture missing content_id",
            reason_codes=("identity_error",),
        )
    return cid


def _coverage_from_fixtures(fixtures: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    covered: set[str] = set()
    for fixture in fixtures:
        covered.update(str(c) for c in fixture.get("categories", ()))
    required = list(REQUIRED_COVERAGE_CATEGORIES)
    missing = [c for c in required if c not in covered]
    if missing:
        raise FixtureValidationError(
            f"fixture corpus missing categories: {', '.join(missing)}",
            reason_codes=("coverage_gap",),
        )
    for ucan in REQUIRED_UCAN_VARIANTS:
        if ucan not in covered:
            raise FixtureValidationError(
                f"missing UCAN variant category {ucan}",
                reason_codes=("coverage_gap",),
            )
    return {
        "required_categories": required,
        "covered_categories": sorted(covered),
        "complete": True,
    }


def _blockers_from_fixtures(fixtures: Sequence[Mapping[str, Any]]) -> list[str]:
    found: set[str] = set()
    for fixture in fixtures:
        found.update(str(b) for b in fixture.get("blocker_refs", ()))
    missing = [b for b in CONFIRMED_BLOCKERS if b not in found]
    if missing:
        raise FixtureValidationError(
            f"fixture corpus missing confirmed blockers: {', '.join(missing)}",
            reason_codes=("blocker_gap",),
        )
    return list(CONFIRMED_BLOCKERS)


def build_manifest(
    fixtures: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a content-identified FixtureManifest@1 over expanded fixtures."""
    expanded = tuple(fixtures) if fixtures is not None else expand_all_recipes()
    coverage = _coverage_from_fixtures(expanded)
    blockers = _blockers_from_fixtures(expanded)
    entries: list[dict[str, Any]] = []
    for f in expanded:
        fault_schedule = f.get("fault_schedule")
        entries.append(
            {
                "fixture_id": f["fixture_id"],
                "content_id": f["content_id"],
                "subsystem": f["subsystem"],
                "polarity": f["polarity"],
                "categories": list(f.get("categories") or ()),
                "blocker_refs": list(f.get("blocker_refs") or ()),
                "trace_content_id": (f.get("expected_trace") or {}).get("content_id"),
                "fault_schedule_content_id": (
                    fault_schedule.get("content_id") if fault_schedule else None
                ),
            }
        )
    body = {
        "schema": FIXTURE_MANIFEST_SCHEMA,
        "manifest_id": MANIFEST_ID,
        "interface": INTERFACE_BUNDLE,
        "fixture_count": len(entries),
        "fixtures": entries,
        "coverage": coverage,
        "confirmed_blockers": blockers,
        "finite": True,
        "safe": True,
        "hermetic": True,
        "recipe_driven": True,
    }
    manifest = _with_content_id(body)
    validate_manifest(manifest)
    return manifest


def load_manifest() -> dict[str, Any]:
    """Load (build) the hermetic fixture manifest.

    Fixtures are recipe-generated in-process so the corpus stays compact and
    never depends on bulk golden envelope dumps.
    """
    return build_manifest()


def materialize_fixture_index(directory: Path | None = None) -> Path:
    """Optionally write a compact index JSON next to the package (for inspection).

    The authoritative corpus remains the recipe expander; the index is a
    derivative cache of fixture_id → content_id pairs only.
    """
    package_dir = Path(__file__).resolve().parent
    target = directory if directory is not None else package_dir
    target.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest()
    index = {
        "schema": FIXTURE_MANIFEST_SCHEMA,
        "manifest_id": manifest["manifest_id"],
        "content_id": manifest["content_id"],
        "fixture_count": manifest["fixture_count"],
        "fixtures": [
            {
                "fixture_id": e["fixture_id"],
                "content_id": e["content_id"],
                "categories": e["categories"],
            }
            for e in manifest["fixtures"]
        ],
    }
    path = target / "fixture_index.json"
    path.write_text(canonical_json(index), encoding="utf-8")
    return path

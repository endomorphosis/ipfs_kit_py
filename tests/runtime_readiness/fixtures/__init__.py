"""Hermetic adversarial state-machine and fault fixtures (KITA-003).

Public surface:
- expand recipes into content-identified RuntimeReadinessFixture records
- validate FaultSchedule and ExpectedStateTrace invariants
- enforce finite, safe, offline fixture bounds

Interfaces:
- RuntimeReadinessFixture@1
- FaultSchedule@1
- ExpectedStateTrace@1
"""

from __future__ import annotations

from .catalog import (
    CONFIRMED_BLOCKERS,
    REQUIRED_COVERAGE_CATEGORIES,
    REQUIRED_UCAN_VARIANTS,
)
from .expand import (
    build_manifest,
    expand_all_recipes,
    expand_recipe,
    fixture_content_id,
    load_manifest,
)
from .recipes import RECIPE_CATALOG, all_recipes
from .safety import SafetyViolation, assert_fixture_safe, validate_fixture_safety
from .schema import (
    EXPECTED_STATE_TRACE_SCHEMA,
    FAULT_SCHEDULE_SCHEMA,
    FIXTURE_MANIFEST_SCHEMA,
    RUNTIME_READINESS_FIXTURE_SCHEMA,
    FixtureValidationError,
    validate_expected_state_trace,
    validate_fault_schedule,
    validate_fixture,
    validate_manifest,
)

__all__ = [
    "CONFIRMED_BLOCKERS",
    "EXPECTED_STATE_TRACE_SCHEMA",
    "FAULT_SCHEDULE_SCHEMA",
    "FIXTURE_MANIFEST_SCHEMA",
    "REQUIRED_COVERAGE_CATEGORIES",
    "REQUIRED_UCAN_VARIANTS",
    "RUNTIME_READINESS_FIXTURE_SCHEMA",
    "RECIPE_CATALOG",
    "FixtureValidationError",
    "SafetyViolation",
    "all_recipes",
    "assert_fixture_safe",
    "build_manifest",
    "expand_all_recipes",
    "expand_recipe",
    "fixture_content_id",
    "load_manifest",
    "validate_expected_state_trace",
    "validate_fault_schedule",
    "validate_fixture",
    "validate_fixture_safety",
    "validate_manifest",
]

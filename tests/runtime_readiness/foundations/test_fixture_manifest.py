"""Validation for KITA-003 hermetic adversarial fixture corpus.

Asserts:
- RuntimeReadinessFixture@1 / FaultSchedule@1 / ExpectedStateTrace@1 validity
- every confirmed blocker and acceptance coverage category is present
- expected traces and faults are finite, safe, and content-identified
- recipe expansion is deterministic
"""

from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from tests.runtime_readiness.fixtures import (
    CONFIRMED_BLOCKERS,
    EXPECTED_STATE_TRACE_SCHEMA,
    FAULT_SCHEDULE_SCHEMA,
    FIXTURE_MANIFEST_SCHEMA,
    REQUIRED_COVERAGE_CATEGORIES,
    REQUIRED_UCAN_VARIANTS,
    RUNTIME_READINESS_FIXTURE_SCHEMA,
    FixtureValidationError,
    SafetyViolation,
    all_recipes,
    assert_fixture_safe,
    build_manifest,
    expand_all_recipes,
    expand_recipe,
    load_manifest,
    validate_expected_state_trace,
    validate_fault_schedule,
    validate_fixture,
    validate_manifest,
)
from tests.runtime_readiness.fixtures.expand import canonical_json, content_id_for
from tests.runtime_readiness.fixtures.recipes import (
    assert_blockers_covered,
    covered_blockers,
)
from tests.runtime_readiness.fixtures.safety import assert_corpus_safe

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def _fixtures() -> tuple[dict[str, Any], ...]:
    return expand_all_recipes()


def _manifest() -> dict[str, Any]:
    return load_manifest()


def test_fixtures_package_layout_exists() -> None:
    assert FIXTURES_DIR.is_dir()
    for name in (
        "__init__.py",
        "schema.py",
        "catalog.py",
        "recipes.py",
        "expand.py",
        "safety.py",
    ):
        assert (FIXTURES_DIR / name).is_file(), f"missing {name}"


def test_fixture_modules_import_cleanly() -> None:
    mod = importlib.import_module("tests.runtime_readiness.fixtures")
    assert mod.RUNTIME_READINESS_FIXTURE_SCHEMA
    assert callable(mod.expand_all_recipes)
    assert callable(mod.build_manifest)


def test_schema_identities_are_versioned() -> None:
    assert RUNTIME_READINESS_FIXTURE_SCHEMA.endswith("@1")
    assert FAULT_SCHEDULE_SCHEMA.endswith("@1")
    assert EXPECTED_STATE_TRACE_SCHEMA.endswith("@1")
    assert FIXTURE_MANIFEST_SCHEMA.endswith("@1")
    assert "runtime-readiness" in RUNTIME_READINESS_FIXTURE_SCHEMA


def test_recipes_cover_every_confirmed_blocker() -> None:
    assert_blockers_covered()
    found = covered_blockers()
    assert set(CONFIRMED_BLOCKERS) <= found
    assert len(found) >= len(CONFIRMED_BLOCKERS)


def test_manifest_covers_required_categories() -> None:
    manifest = _manifest()
    covered = set(manifest["coverage"]["covered_categories"])
    required = set(REQUIRED_COVERAGE_CATEGORIES)
    assert required <= covered
    for ucan in REQUIRED_UCAN_VARIANTS:
        assert ucan in covered


def test_every_acceptance_category_has_at_least_one_fixture() -> None:
    fixtures = _fixtures()
    by_cat: dict[str, list[str]] = {c: [] for c in REQUIRED_COVERAGE_CATEGORIES}
    for fixture in fixtures:
        for cat in fixture["categories"]:
            if cat in by_cat:
                by_cat[cat].append(fixture["fixture_id"])
    missing = [c for c, ids in by_cat.items() if not ids]
    assert not missing, f"categories without fixtures: {missing}"


def test_rename_move_and_bucket_saga_and_wal_and_arc_present() -> None:
    fixtures = _fixtures()
    ids = [f["fixture_id"] for f in fixtures]
    assert any("rename" in i or "move" in i for i in ids)
    assert any("bucket" in i for i in ids)
    assert any("wal" in i for i in ids)
    assert any("arc" in i for i in ids)
    assert any("replica" in i for i in ids)
    assert any("ucan" in i for i in ids)


def test_ucan_variants_are_distinct_fixtures() -> None:
    fixtures = _fixtures()
    for variant in REQUIRED_UCAN_VARIANTS:
        matches = [f for f in fixtures if variant in f["categories"]]
        assert matches, f"no fixture for {variant}"
        for fixture in matches:
            assert fixture["subsystem"] == "ucan"
            terminal = fixture["expected_trace"]["terminal"]
            assert terminal["outcome"] in frozenset(
                {"denied", "contract_violation_observed"}
            )


def test_expand_all_recipes_produces_valid_fixtures() -> None:
    fixtures = _fixtures()
    assert len(fixtures) == len(all_recipes())
    for fixture in fixtures:
        validate_fixture(fixture)
        assert fixture["schema"] == RUNTIME_READINESS_FIXTURE_SCHEMA
        assert fixture["hermetic"] is True
        assert fixture["finite"] is True
        assert fixture["content_id"].startswith("sha256:")


def test_expected_traces_and_faults_are_finite_safe_content_identified() -> None:
    fixtures = _fixtures()
    for fixture in fixtures:
        trace = fixture["expected_trace"]
        validate_expected_state_trace(trace)
        assert trace["schema"] == EXPECTED_STATE_TRACE_SCHEMA
        assert trace["finite"] is True
        assert trace["safe"] is True
        assert trace["content_id"].startswith("sha256:")
        for step in trace["steps"]:
            assert step["content_id"].startswith("sha256:")
        schedule = fixture.get("fault_schedule")
        if schedule is not None:
            validate_fault_schedule(schedule)
            assert schedule["schema"] == FAULT_SCHEDULE_SCHEMA
            assert schedule["finite"] is True
            assert schedule["safe"] is True
            assert schedule["content_id"].startswith("sha256:")
            for fault in schedule["faults"]:
                assert fault["content_id"].startswith("sha256:")


def test_corpus_is_hermetic_safe() -> None:
    fixtures = _fixtures()
    assert_corpus_safe(fixtures)
    for fixture in fixtures:
        assert_fixture_safe(fixture)
        safety = fixture["safety"]
        for flag in (
            "network",
            "credentials",
            "user_paths",
            "executable_payloads",
            "production_side_effects",
        ):
            assert safety[flag] is False


def test_manifest_is_valid_and_content_identified() -> None:
    manifest = _manifest()
    validate_manifest(manifest)
    assert manifest["schema"] == FIXTURE_MANIFEST_SCHEMA
    assert manifest["finite"] is True
    assert manifest["safe"] is True
    assert manifest["hermetic"] is True
    assert manifest["recipe_driven"] is True
    assert manifest["fixture_count"] == len(manifest["fixtures"])
    assert manifest["content_id"].startswith("sha256:")
    assert set(manifest["confirmed_blockers"]) == set(CONFIRMED_BLOCKERS)


def test_manifest_fixture_content_ids_match_expanded_fixtures() -> None:
    fixtures = {f["fixture_id"]: f for f in _fixtures()}
    manifest = _manifest()
    for entry in manifest["fixtures"]:
        fixture = fixtures[entry["fixture_id"]]
        assert entry["content_id"] == fixture["content_id"]
        assert entry["trace_content_id"] == fixture["expected_trace"]["content_id"]
        if fixture.get("fault_schedule") is None:
            assert entry.get("fault_schedule_content_id") is None
        else:
            assert (
                entry["fault_schedule_content_id"]
                == fixture["fault_schedule"]["content_id"]
            )


def test_expansion_is_deterministic() -> None:
    first = expand_all_recipes()
    second = expand_all_recipes()
    assert [f["content_id"] for f in first] == [f["content_id"] for f in second]
    assert build_manifest()["content_id"] == build_manifest()["content_id"]
    assert canonical_json(first[0]) == canonical_json(second[0])


def test_content_id_matches_body_hash() -> None:
    for recipe in all_recipes():
        fixture = expand_recipe(recipe)
        body = {k: v for k, v in fixture.items() if k != "content_id"}
        assert fixture["content_id"] == content_id_for(body)


def test_rejects_network_locator_in_fixture_payload() -> None:
    fixture = dict(expand_recipe(all_recipes()[0]))
    fixture["description"] = "fetch https://example.invalid/payload"
    with pytest.raises(SafetyViolation, match="network locator"):
        assert_fixture_safe(fixture)


def test_rejects_secret_like_keys() -> None:
    fixture = dict(expand_recipe(all_recipes()[0]))
    bad_state = dict(fixture["initial_state"])
    bad_state["api_key"] = "should-not-appear"
    fixture["initial_state"] = bad_state
    with pytest.raises((SafetyViolation, FixtureValidationError)):
        validate_fixture(fixture)
    with pytest.raises(SafetyViolation):
        assert_fixture_safe(fixture)


def test_rejects_wrong_schema_identity() -> None:
    fixture = dict(expand_recipe(all_recipes()[0]))
    fixture["schema"] = "forged/schema@9"
    with pytest.raises(FixtureValidationError, match="schema"):
        validate_fixture(fixture)


def test_rejects_non_finite_float_in_trace() -> None:
    fixture = expand_recipe(all_recipes()[0])
    trace = json.loads(canonical_json(fixture["expected_trace"]))
    trace["steps"][0]["state_snapshot"] = {"nan_value": float("nan")}
    with pytest.raises(FixtureValidationError, match="non-finite"):
        validate_expected_state_trace(trace)


def test_rejects_empty_trace() -> None:
    with pytest.raises(FixtureValidationError, match="non-empty"):
        validate_expected_state_trace(
            {
                "schema": EXPECTED_STATE_TRACE_SCHEMA,
                "trace_id": "trace:empty@1",
                "steps": [],
                "terminal": {
                    "outcome": "success",
                    "namespace": {},
                    "evidence": {},
                },
            }
        )


def test_rejects_unknown_fault_kind() -> None:
    with pytest.raises(FixtureValidationError, match="unknown fault kind"):
        validate_fault_schedule(
            {
                "schema": FAULT_SCHEDULE_SCHEMA,
                "schedule_id": "fault-schedule:x@1",
                "faults": [
                    {
                        "kind": "launch_missiles",
                        "at_operation_index": 0,
                        "effects": [],
                        "parameters": {},
                    }
                ],
            }
        )


def test_rejects_manifest_with_coverage_gap() -> None:
    manifest = dict(_manifest())
    coverage = dict(manifest["coverage"])
    coverage["covered_categories"] = [
        c for c in coverage["covered_categories"] if c != "resource_exhaustion"
    ]
    manifest["coverage"] = coverage
    with pytest.raises(FixtureValidationError, match="coverage missing"):
        validate_manifest(manifest)


def test_rejects_duplicate_fixture_ids_in_manifest() -> None:
    manifest = dict(_manifest())
    fixtures = list(manifest["fixtures"])
    fixtures.append(dict(fixtures[0]))
    manifest["fixtures"] = fixtures
    with pytest.raises(FixtureValidationError, match="duplicate fixture_id"):
        validate_manifest(manifest)


def test_corpus_includes_positive_and_adversarial_polarities() -> None:
    fixtures = _fixtures()
    polarities = {f["polarity"] for f in fixtures}
    assert "adversarial" in polarities
    assert "positive" in polarities


def test_adversarial_rename_observes_silent_success_contract_violation() -> None:
    fixtures = _fixtures()
    adversarial = [
        f
        for f in fixtures
        if "rename" in f["fixture_id"]
        and f["polarity"] == "adversarial"
        and "confirmed_blocker" in f["categories"]
    ]
    assert adversarial
    for fixture in adversarial:
        terminal = fixture["expected_trace"]["terminal"]
        assert terminal["outcome"] == "contract_violation_observed"
        evidence = terminal["evidence"]
        assert evidence.get("mutated") is False
        assert evidence.get("reported_success") is True


def test_positive_rename_mutates_namespace() -> None:
    positive = [
        f
        for f in _fixtures()
        if f["polarity"] == "positive" and "rename_move" in f["categories"]
    ]
    assert positive
    for fixture in positive:
        terminal = fixture["expected_trace"]["terminal"]
        assert terminal["outcome"] == "success"
        assert terminal["evidence"].get("mutated") is True


def test_recipe_slugs_are_unique() -> None:
    slugs = [r["slug"] for r in all_recipes()]
    assert len(slugs) == len(set(slugs))


def test_build_manifest_matches_load_manifest() -> None:
    assert build_manifest()["content_id"] == load_manifest()["content_id"]


def test_no_live_credentials_or_user_home_strings_in_corpus() -> None:
    payload = canonical_json(_fixtures()).lower()
    for banned in (
        "password=",
        "secret_key",
        "begin private key",
        "/home/",
        "/users/",
        "$home",
        "https://",
        "http://",
    ):
        assert banned not in payload


def test_fixture_content_ids_are_unique() -> None:
    fixtures = _fixtures()
    ids = [f["content_id"] for f in fixtures]
    fixture_ids = [f["fixture_id"] for f in fixtures]
    assert len(ids) == len(set(ids))
    assert len(fixture_ids) == len(set(fixture_ids))


def test_sha256_content_ids_are_hex_and_recomputable() -> None:
    fixtures = _fixtures()
    for fixture in fixtures:
        digest = fixture["content_id"].removeprefix("sha256:")
        assert len(digest) == 64
        int(digest, 16)
        body = {k: v for k, v in fixture.items() if k != "content_id"}
        assert fixture["content_id"] == content_id_for(body)
        trace = fixture["expected_trace"]
        trace_body = {k: v for k, v in trace.items() if k != "content_id"}
        assert trace["content_id"] == content_id_for(trace_body)

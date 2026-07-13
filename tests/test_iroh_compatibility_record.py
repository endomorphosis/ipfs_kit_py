"""Offline conformance tests for the IROH-001 compatibility decision."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError


ROOT = Path(__file__).resolve().parents[1]
DECISION_PATH = ROOT / "docs" / "iroh" / "compatibility.md"
RESOURCES = ROOT / "ipfs_kit_py" / "resources"
RELEASE_PATH = RESOURCES / "iroh-releases.json"
RELEASE_SCHEMA_PATH = RESOURCES / "iroh-releases.schema.json"
FIXTURE_SCHEMA_PATH = RESOURCES / "iroh-version-fixture.schema.json"
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "iroh" / "version"

EXPECTED_COMPONENTS = {
    "iroh": "1.0.2",
    "iroh-blobs": "0.103.0",
    "iroh-docs": "0.101.0",
    "iroh-gossip": "0.101.0",
}
EXPECTED_PLATFORMS = {
    "linux_x86_64_gnu",
    "linux_x86_64_musl",
    "linux_aarch64_gnu",
    "linux_aarch64_musl",
    "macos_x86_64",
    "macos_aarch64",
    "windows_x86_64",
}
VERSION_LINE = re.compile(
    r"^ipfs-kit-iroh-sidecar (?P<sidecar>[^ ]+) "
    r"\(protocol (?P<protocol>[0-9]+); iroh (?P<iroh>[^;]+); "
    r"iroh-blobs (?P<blobs>[^;]+); iroh-docs (?P<docs>[^;]+); "
    r"iroh-gossip (?P<gossip>[^)]+)\)\n$"
)


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    assert isinstance(value, dict), f"{path} must contain a JSON object"
    return value


@pytest.fixture(scope="module")
def release_schema() -> dict[str, Any]:
    return _read_json(RELEASE_SCHEMA_PATH)


@pytest.fixture(scope="module")
def fixture_schema() -> dict[str, Any]:
    return _read_json(FIXTURE_SCHEMA_PATH)


@pytest.fixture(scope="module")
def release() -> dict[str, Any]:
    return _read_json(RELEASE_PATH)


def _validator(schema: dict[str, Any]) -> Draft202012Validator:
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def test_schemas_are_valid_draft_2020_12(
    release_schema: dict[str, Any], fixture_schema: dict[str, Any]
) -> None:
    assert release_schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert fixture_schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    _validator(release_schema)
    _validator(fixture_schema)


def test_release_record_validates(
    release: dict[str, Any], release_schema: dict[str, Any]
) -> None:
    _validator(release_schema).validate(release)


def test_human_decision_identifies_the_machine_record_and_bundle(
    release: dict[str, Any]
) -> None:
    decision = DECISION_PATH.read_text(encoding="utf-8")
    assert f"Decision: {release['decision_id']}" in decision
    assert f"Release bundle: `{release['release_bundle']['id']}`" in decision
    assert "ipfs_kit_py/resources/iroh-releases.json" in decision
    assert "## Breaking-version boundaries" in decision
    assert "## Upgrade and rollback procedure" in decision


def test_pinned_bundle_and_version_output_are_cross_field_consistent(
    release: dict[str, Any]
) -> None:
    components = {item["crate"]: item["version"] for item in release["components"]}
    assert components == EXPECTED_COMPONENTS
    assert release["release_bundle"] == {
        "id": "iroh-1.0.2-ipfs-kit.1",
        "status": "supported",
        "rust_version": "1.91",
        "protocol_version": 1,
    }

    match = VERSION_LINE.fullmatch(release["sidecar"]["version_stdout"])
    assert match is not None
    assert match.groupdict() == {
        "sidecar": release["sidecar"]["version"],
        "protocol": str(release["release_bundle"]["protocol_version"]),
        "iroh": components["iroh"],
        "blobs": components["iroh-blobs"],
        "docs": components["iroh-docs"],
        "gossip": components["iroh-gossip"],
    }

    for component in release["components"]:
        crate = component["crate"]
        version = component["version"]
        assert component["source"] == (
            f"https://crates.io/api/v1/crates/{crate}/{version}/download"
        )
        assert component["checksum_source"] == (
            f"https://crates.io/api/v1/crates/{crate}/{version}"
        )
        assert component["tag"] == f"v{version}"


def test_every_platform_has_exactly_one_valid_version_fixture(
    release: dict[str, Any], fixture_schema: dict[str, Any]
) -> None:
    validator = _validator(fixture_schema)
    platforms = release["platforms"]
    platform_ids = [platform["id"] for platform in platforms]
    assert len(platform_ids) == len(set(platform_ids))
    assert set(platform_ids) == EXPECTED_PLATFORMS

    recorded_paths = {ROOT / platform["version_fixture"] for platform in platforms}
    actual_paths = set(FIXTURE_DIR.glob("*.json"))
    assert recorded_paths == actual_paths

    for platform in platforms:
        fixture_path = ROOT / platform["version_fixture"]
        assert fixture_path.resolve().is_relative_to(FIXTURE_DIR.resolve())
        fixture = _read_json(fixture_path)
        validator.validate(fixture)
        assert fixture_path.stem == fixture["platform_id"] == platform["id"]
        assert fixture["command"] == release["sidecar"]["version_command"]
        assert fixture["stdout"] == release["sidecar"]["version_stdout"]
        assert fixture["stderr"] == ""
        assert fixture["exit_code"] == 0
        assert fixture["fixture_kind"] == "contract-golden"
        assert not platform["installable"]


def test_source_pinned_record_cannot_claim_installable_artifacts(
    release: dict[str, Any], release_schema: dict[str, Any]
) -> None:
    invalid = copy.deepcopy(release)
    platform = invalid["platforms"][0]
    platform.update(
        {
            "installable": True,
            "url": "https://github.com/endomorphosis/ipfs_kit_py/releases/download/v0.1.0/archive.tar.gz",
            "size": 1,
            "checksum_sha256": "0" * 64,
        }
    )
    with pytest.raises(ValidationError):
        _validator(release_schema).validate(invalid)


def test_published_record_requires_artifact_identity_for_every_platform(
    release: dict[str, Any], release_schema: dict[str, Any]
) -> None:
    invalid = copy.deepcopy(release)
    invalid["sidecar"]["distribution_status"] = "published"
    for platform in invalid["platforms"]:
        platform["installable"] = True
    with pytest.raises(ValidationError):
        _validator(release_schema).validate(invalid)


def test_release_schema_rejects_drift_and_unknown_fields(
    release: dict[str, Any], release_schema: dict[str, Any]
) -> None:
    validator = _validator(release_schema)

    wrong_component = copy.deepcopy(release)
    wrong_component["components"][0]["crate"] = "iroh-blobs"
    with pytest.raises(ValidationError):
        validator.validate(wrong_component)

    unknown_field = copy.deepcopy(release)
    unknown_field["allow_unverified_downloads"] = True
    with pytest.raises(ValidationError):
        validator.validate(unknown_field)


def test_fixture_schema_rejects_unrecorded_or_malformed_results(
    fixture_schema: dict[str, Any]
) -> None:
    validator = _validator(fixture_schema)
    fixture = _read_json(FIXTURE_DIR / "linux_x86_64_gnu.json")

    malformed = copy.deepcopy(fixture)
    malformed["stdout"] = malformed["stdout"].rstrip("\n")
    with pytest.raises(ValidationError):
        validator.validate(malformed)

    fake_capture = copy.deepcopy(fixture)
    fake_capture["fixture_kind"] = "artifact-capture"
    with pytest.raises(ValidationError):
        validator.validate(fake_capture)

"""Contract tests for the audited Iroh release bundle."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
RESOURCE_DIR = ROOT / "ipfs_kit_py" / "resources"
DECISION_PATH = ROOT / "docs" / "iroh" / "compatibility.md"
RELEASE_PATH = RESOURCE_DIR / "iroh-releases.json"
SCHEMA_PATH = RESOURCE_DIR / "iroh-releases.schema.json"
VERSION_FIXTURE_SCHEMA_PATH = RESOURCE_DIR / "iroh-version-fixture.schema.json"


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Fail when JSON would otherwise silently discard an earlier key."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream, object_pairs_hook=_reject_duplicate_keys)


def test_all_iroh_json_contract_files_reject_duplicate_object_keys() -> None:
    paths = [RELEASE_PATH, SCHEMA_PATH, VERSION_FIXTURE_SCHEMA_PATH]
    paths.extend(sorted((ROOT / "tests/fixtures/iroh/version").glob("*.json")))

    for path in paths:
        assert _load(path), path


def test_human_decision_record_names_machine_authority_and_required_domains() -> None:
    decision = DECISION_PATH.read_text(encoding="utf-8")

    assert "Decision: IROH-001" in decision
    assert "(../../ipfs_kit_py/resources/iroh-releases.json)" in decision
    for heading in (
        "## Decision",
        "## Why there is an IPFS Kit sidecar",
        "## Platforms and distribution gate",
        "## Supply-chain verification",
        "## Data-format boundaries",
        "## Breaking boundaries",
        "## Upgrade and rollback procedure",
        "## Validation",
    ):
        assert heading in decision


def test_release_record_validates_against_draft_2020_12_schema() -> None:
    schema = _load(SCHEMA_PATH)
    release = _load(RELEASE_PATH)

    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER,
    )
    errors = sorted(validator.iter_errors(release), key=lambda error: list(error.path))
    assert not errors, "\n".join(error.message for error in errors)


def test_component_bundle_is_complete_and_exactly_pinned() -> None:
    release = _load(RELEASE_PATH)
    components = {component["crate"]: component for component in release["components"]}

    assert len(components) == len(release["components"])
    assert {
        name: (
            component["version"],
            component["checksum_sha256"],
            component["commit"],
        )
        for name, component in components.items()
    } == {
        "iroh": (
            "1.0.2",
            "5fca9b4b462c343ff88fc0af4096c186f939b602a0bc08723536ef2c31c93971",
            "c3ccf502c3881444811fbb3a3a0eeaf850594dba",
        ),
        "iroh-blobs": (
            "0.103.0",
            "5be50b0e2d0a9ba65cee4e0dfb708b3704e02ad12bd4c14c6307e94245943126",
            "e82cbdcbdac9a78033174aad55e3199b2cf4c0dc",
        ),
        "iroh-docs": (
            "0.101.0",
            "8fd1bd5e39d0321a3c4a2bcef9650476c076e2df41a0e84577eca23d6de6c8ab",
            "091e8cac47bbc49cdb84b0bfed227cc163b61dfe",
        ),
        "iroh-gossip": (
            "0.101.0",
            "4e1dc4b05f73e7a1b9e83b531eb63c3fd671b0af3aeb13b59c546dd7ca747515",
            "2ce78afe09d89d41d123f28eac19bdc831609cc8",
        ),
    }
    assert all(
        component["checksum_source"]
        == f"https://crates.io/api/v1/crates/{component['crate']}/{component['version']}"
        for component in components.values()
    )
    assert all(
        component["source"] == f"{component['checksum_source']}/download"
        for component in components.values()
    )
    assert all(
        component["tag"] == f"v{component['version']}" for component in components.values()
    )
    assert {name: component["repository"] for name, component in components.items()} == {
        "iroh": "https://github.com/n0-computer/iroh",
        "iroh-blobs": "https://github.com/n0-computer/iroh-blobs",
        "iroh-docs": "https://github.com/n0-computer/iroh-docs",
        "iroh-gossip": "https://github.com/n0-computer/iroh-gossip",
    }
    assert {component["license"] for component in components.values()} == {
        "MIT OR Apache-2.0",
        "MIT/Apache-2.0",
    }
    assert all(component["default_features"] is True for component in components.values())
    assert {name: set(component["features"]) for name, component in components.items()} == {
        "iroh": {"fast-apple-datapath", "metrics", "portmapper", "tls-ring"},
        "iroh-blobs": {"fs-store", "hide-proto-docs", "metrics", "rpc"},
        "iroh-docs": {"fs-store", "metrics", "redb-v2-migration", "rpc"},
        "iroh-gossip": {"metrics", "net"},
    }


def test_sidecar_version_contract_is_derived_from_the_selected_bundle() -> None:
    release = _load(RELEASE_PATH)
    components = {component["crate"]: component for component in release["components"]}
    sidecar = release["sidecar"]

    expected_stdout = (
        f"{sidecar['binary']} {sidecar['version']} "
        f"(protocol {release['release_bundle']['protocol_version']}; "
        f"iroh {components['iroh']['version']}; "
        f"iroh-blobs {components['iroh-blobs']['version']}; "
        f"iroh-docs {components['iroh-docs']['version']}; "
        f"iroh-gossip {components['iroh-gossip']['version']})\n"
    )

    assert sidecar["version_command"] == [sidecar["binary"], "--version"]
    assert sidecar["version_stdout"] == expected_stdout
    assert all(
        component["rust_version"] == release["release_bundle"]["rust_version"]
        for component in components.values()
    )


def test_each_supported_platform_has_a_matching_version_fixture() -> None:
    release = _load(RELEASE_PATH)
    fixture_schema = _load(VERSION_FIXTURE_SCHEMA_PATH)
    jsonschema.Draft202012Validator.check_schema(fixture_schema)
    fixture_validator = jsonschema.Draft202012Validator(
        fixture_schema,
        format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER,
    )
    platforms = release["platforms"]
    ids = [platform["id"] for platform in platforms]

    assert len(ids) == len(set(ids))
    assert {platform["rust_target"] for platform in platforms} == {
        "x86_64-unknown-linux-gnu",
        "x86_64-unknown-linux-musl",
        "aarch64-unknown-linux-gnu",
        "aarch64-unknown-linux-musl",
        "x86_64-apple-darwin",
        "aarch64-apple-darwin",
        "x86_64-pc-windows-msvc",
    }

    for platform in platforms:
        fixture_path = ROOT / platform["version_fixture"]
        assert fixture_path.is_file(), fixture_path
        fixture = _load(fixture_path)
        fixture_validator.validate(fixture)
        base_fields = {
            "schema_version",
            "fixture_kind",
            "platform_id",
            "command",
            "exit_code",
            "stdout",
            "stderr",
        }
        assert fixture["schema_version"] == 1
        assert fixture["platform_id"] == platform["id"]
        assert fixture["command"] == release["sidecar"]["version_command"]
        assert fixture["exit_code"] == 0
        assert fixture["stdout"] == release["sidecar"]["version_stdout"]
        assert fixture["stderr"] == ""
        if release["sidecar"]["distribution_status"] == "published":
            assert set(fixture) == base_fields | {"captured_at", "artifact_sha256"}
            assert fixture["fixture_kind"] == "artifact-capture"
            assert fixture["artifact_sha256"] == platform["checksum_sha256"]
        else:
            assert set(fixture) == base_fields
            assert fixture["fixture_kind"] == "contract-golden"

    fixture_dir = ROOT / "tests" / "fixtures" / "iroh" / "version"
    assert {path.resolve() for path in fixture_dir.glob("*.json")} == {
        (ROOT / platform["version_fixture"]).resolve() for platform in platforms
    }


def test_unpublished_platforms_cannot_be_installed() -> None:
    release = _load(RELEASE_PATH)

    assert release["sidecar"]["distribution_status"] == "source-pinned"
    assert all(platform["installable"] is False for platform in release["platforms"])
    assert release["verification"]["fail_closed"] is True


def test_schema_enforces_distribution_state_installability_gate() -> None:
    schema = _load(SCHEMA_PATH)
    release = _load(RELEASE_PATH)
    validator = jsonschema.Draft202012Validator(schema)

    unpublished = deepcopy(release)
    unpublished["platforms"][0].update(
        installable=True,
        url="https://downloads.example.invalid/sidecar.tar.gz",
        size=1,
        checksum_sha256="0" * 64,
    )
    assert not validator.is_valid(unpublished)

    withdrawn = deepcopy(unpublished)
    withdrawn["sidecar"]["distribution_status"] = "withdrawn"
    assert not validator.is_valid(withdrawn)

    published = deepcopy(release)
    published["sidecar"]["distribution_status"] = "published"
    assert not validator.is_valid(published)

    for index, platform in enumerate(published["platforms"], start=1):
        platform.update(
            installable=True,
            url=f"https://github.com/endomorphosis/ipfs_kit_py/releases/download/"
            f"iroh-sidecar-v0.1.0/{platform['id']}.archive",
            size=index,
            checksum_sha256=f"{index:064x}",
        )
    assert validator.is_valid(published)


def test_supply_chain_authorities_are_machine_readable_and_fail_closed() -> None:
    release = _load(RELEASE_PATH)
    verification = release["verification"]

    assert verification["source_archives"] == {
        "algorithm": "sha256",
        "authority": "crates.io",
        "metadata_url_template": "https://crates.io/api/v1/crates/{crate}/{version}",
        "download_url_template": "https://crates.io/api/v1/crates/{crate}/{version}/download",
    }
    artifacts = verification["sidecar_artifacts"]
    assert artifacts["algorithm"] == "sha256"
    assert artifacts["authority"] == "github-release-assets"
    assert artifacts["release_repository"] == "https://github.com/endomorphosis/ipfs_kit_py"
    assert artifacts["attestation"] == {
        "required": True,
        "authority": "github-artifact-attestations",
        "detached_upstream_signatures_available": False,
        "verification_command": [
            "gh",
            "attestation",
            "verify",
            "{artifact}",
            "--repo",
            "endomorphosis/ipfs_kit_py",
        ],
    }
    assert verification["fail_closed"] is True


def test_schema_requires_supply_chain_metadata_for_installable_artifacts() -> None:
    schema = _load(SCHEMA_PATH)
    release = _load(RELEASE_PATH)
    validator = jsonschema.Draft202012Validator(schema)

    candidate = deepcopy(release)
    candidate["platforms"][0]["installable"] = True
    errors = list(validator.iter_errors(candidate))
    assert errors
    assert {
        required
        for error in errors
        for required in ("url", "size", "checksum_sha256")
        if required in error.message
    } == {
        "url",
        "size",
        "checksum_sha256",
    }

    candidate = deepcopy(release)
    candidate["platforms"][0].update(
        installable=True,
        url="http://downloads.example.invalid/sidecar.tar.gz",
        size=1,
        checksum_sha256="0" * 64,
    )
    assert any(
        "does not match" in error.message for error in validator.iter_errors(candidate)
    )

    candidate["platforms"][0]["url"] = (
        "https://github.com/untrusted/ipfs_kit_py/releases/download/"
        "iroh-sidecar-v0.1.0/sidecar.tar.gz"
    )
    assert any(
        "does not match" in error.message for error in validator.iter_errors(candidate)
    )


def test_schema_rejects_incomplete_or_incoherent_bundle_members() -> None:
    schema = _load(SCHEMA_PATH)
    release = _load(RELEASE_PATH)
    validator = jsonschema.Draft202012Validator(schema)

    duplicate_component = deepcopy(release)
    duplicate_component["components"][3] = deepcopy(duplicate_component["components"][2])
    assert not validator.is_valid(duplicate_component)

    duplicate_platform = deepcopy(release)
    duplicate_platform["platforms"][6] = deepcopy(duplicate_platform["platforms"][5])
    assert not validator.is_valid(duplicate_platform)

    incoherent_platform = deepcopy(release)
    incoherent_platform["platforms"][0]["archive_format"] = "zip"
    assert not validator.is_valid(incoherent_platform)


def test_artifact_capture_fixture_requires_provenance() -> None:
    schema = _load(VERSION_FIXTURE_SCHEMA_PATH)
    fixture = _load(ROOT / "tests/fixtures/iroh/version/linux_x86_64_gnu.json")
    fixture["fixture_kind"] = "artifact-capture"

    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(fixture))
    assert errors
    assert any("captured_at" in error.message for error in errors)
    assert any("artifact_sha256" in error.message for error in errors)


def test_version_fixture_schema_rejects_unlisted_platforms() -> None:
    schema = _load(VERSION_FIXTURE_SCHEMA_PATH)
    fixture = _load(ROOT / "tests/fixtures/iroh/version/linux_x86_64_gnu.json")
    fixture["platform_id"] = "linux_riscv64_gnu"

    assert not jsonschema.Draft202012Validator(schema).is_valid(fixture)


def test_machine_record_covers_required_decision_domains() -> None:
    release = _load(RELEASE_PATH)

    assert release["data_formats"]["blob_hash_algorithm"] == "BLAKE3-256"
    assert release["data_formats"]["blob_hash_bytes"] == 32
    assert release["licenses"]["spdx_expression"] == "MIT OR Apache-2.0"
    assert set(release["licenses"]["upstream_notice_files"]) == {
        "LICENSE-MIT",
        "LICENSE-APACHE",
    }
    assert release["upgrade_policy"]["automatic_patch_upgrades"] is False
    assert release["upgrade_policy"]["requires_new_bundle_id"] is True
    assert len(release["upgrade_policy"]["required_steps"]) >= 6

    rpc = release["sidecar"]["rpc"]
    assert rpc["transport"] == "local-ipc"
    assert set(rpc["capability_groups"]) == {"system", "blobs", "manifests", "sync"}
    assert rpc["required_methods"] == [
        "system.version",
        "system.capabilities",
        "system.health",
        "system.shutdown",
        "blobs.ingest",
        "blobs.stat",
        "blobs.read_range",
        "blobs.protect",
        "blobs.release",
        "manifests.open",
        "manifests.create",
        "manifests.read",
        "manifests.compare_and_swap",
        "manifests.history",
        "sync.start",
        "sync.progress",
        "sync.cancel",
        "sync.status",
    ]
    assert release["sidecar"]["cli"]["commands"] == [
        {
            "name": "version",
            "argv": ["ipfs-kit-iroh-sidecar", "--version"],
            "stdout_format": "version-line-v1",
            "side_effect_free": True,
        }
    ]
    assert {item["binary"] for item in release["sidecar"]["upstream_binaries"]} == {
        "iroh-relay",
        "iroh-dns-server",
    }
    assert {
        item["version"] for item in release["sidecar"]["upstream_binaries"]
    } == {"1.0.2"}


def test_schema_and_release_record_are_shipped_as_package_data() -> None:
    """Keep the installer/runtime contract available outside a source checkout."""
    package_data = ROOT / "ipfs_kit_py" / "resources"

    assert RELEASE_PATH.parent == package_data
    assert SCHEMA_PATH.parent == package_data
    assert VERSION_FIXTURE_SCHEMA_PATH.parent == package_data

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.setuptools.package-data]" in pyproject
    assert '"ipfs_kit_py" = ["**/*"]' in pyproject

"""IROH-024 threat-model and executable hardening conformance gates."""

from __future__ import annotations

import copy
import io
import json
import re
import stat
import tarfile
from pathlib import Path

import pytest

from ipfs_kit_py.install_iroh import IrohInstaller, UnsafeArchiveError, load_release_manifest
from ipfs_kit_py.iroh.client import REDACTED, redact
from ipfs_kit_py.iroh.config import (
    RESOURCE_LIMIT_MAXIMUMS,
    IrohServiceConfig,
    ResourceLimits,
    ensure_state_layout,
)
from ipfs_kit_py.iroh.errors import IrohInvalidConfigError, IrohInvalidPathError
from ipfs_kit_py.iroh.governance import GovernedOperationError, MAX_TICKET_BYTES, validate_ticket
from ipfs_kit_py.iroh.manifest import validate_manifest_path
from ipfs_kit_py.iroh.security import (
    SECURITY_REPORT_KIND,
    audit_release_manifest,
    audit_resource_limits,
    audit_state_permissions,
    combine_security_reports,
    run_security_audit,
    scan_log,
    scan_log_bytes,
)

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "ipfs_kit_py" / "resources"
RELEASE = RESOURCES / "iroh-releases.json"
VECTORS = RESOURCES / "iroh-security-vectors.json"
VECTOR_SCHEMA = RESOURCES / "iroh-security-vectors.schema.json"
DOCS = ROOT / "docs" / "iroh"


def test_security_outputs_exist_are_versioned_and_have_no_placeholders() -> None:
    expected = [
        DOCS / "threat-model.md",
        DOCS / "credential-rotation.md",
        VECTORS,
        VECTOR_SCHEMA,
    ]
    for path in expected:
        assert path.is_file(), f"missing IROH-024 output: {path}"
        assert not re.search(
            rb"\b(?:TODO|TBD|FIXME|PLACEHOLDER)\b", path.read_bytes(), re.IGNORECASE
        )
    vectors = json.loads(VECTORS.read_text(encoding="utf-8"))
    schema = json.loads(VECTOR_SCHEMA.read_text(encoding="utf-8"))
    assert vectors["schema_version"] == 1
    assert vectors["kind"] == "ipfs-kit-iroh-security-vectors"
    assert vectors["release_bundle"] == "iroh-1.0.2-ipfs-kit.1"
    assert schema["properties"]["kind"]["const"] == vectors["kind"]


def test_security_vector_catalog_is_closed_unique_and_covers_every_threat() -> None:
    catalog = json.loads(VECTORS.read_text(encoding="utf-8"))
    vectors = catalog["vectors"]
    required_fields = {"id", "threat", "surface", "input", "expected"}
    expected_threats = {
        "malicious-ticket",
        "malicious-peer",
        "malicious-manifest",
        "path-traversal",
        "symlink",
        "archive",
        "key-theft",
        "replay",
        "rollback",
        "resource-exhaustion",
        "rpc-exposure",
        "relay-metadata",
        "supply-chain",
    }
    identifiers = [vector["id"] for vector in vectors]
    assert len(identifiers) == len(set(identifiers))
    assert all(re.fullmatch(r"IROH-SEC-[0-9]{3}", value) for value in identifiers)
    assert {vector["threat"] for vector in vectors} == expected_threats
    for vector in vectors:
        assert set(vector) == required_fields
        assert set(vector["expected"]) == {"outcome", "control", "signal"}
        assert vector["expected"]["outcome"] in {"reject", "redact", "bound", "fail-closed"}


def test_threat_model_maps_assets_boundaries_controls_and_residual_risk() -> None:
    document = (DOCS / "threat-model.md").read_text(encoding="utf-8")
    for heading in (
        "## Security objectives",
        "## Assets and trust boundaries",
        "## Threat analysis and controls",
        "## Security invariants",
        "## Verification and security vectors",
        "## Operational validation and response",
        "## Review triggers and ownership",
    ):
        assert heading in document
    compact = " ".join(document.split()).lower()
    for requirement in (
        "malicious, oversized",
        "authenticated malicious peer",
        "manifest contains unknown fields",
        "traversal",
        "symlink",
        "decompression bomb",
        "node identity",
        "replayed",
        "rollback",
        "resource",
        "rpc is exposed",
        "relay",
        "dependency is substituted",
        "residual risk",
    ):
        assert requirement in compact


def test_rotation_runbook_has_routine_emergency_rollback_and_evidence_steps() -> None:
    document = (DOCS / "credential-rotation.md").read_text(encoding="utf-8")
    for heading in (
        "## Roles, evidence, and prerequisites",
        "## Routine node identity rotation",
        "## Namespace write-capability rotation",
        "## Read-ticket rotation and recipient offboarding",
        "## Emergency compromise rotation",
        "## Acceptance record",
    ):
        assert heading in document
    compact = " ".join(document.split())
    for requirement in (
        "Never paste a raw value",
        "Never start a second node",
        "Rollback is allowed only before old-identity revocation",
        "deleting a provider record does not revoke a copied capability",
        "unique newest verified manifest chain",
        "provider audit IDs",
        "unauthorized read/control/destructive calls",
    ):
        assert requirement in compact


def test_security_document_links_resolve() -> None:
    markdown_link = re.compile(r"\[[^]]+\]\(([^)#]+)(?:#[^)]+)?\)")
    for name in ("security.md", "threat-model.md", "credential-rotation.md"):
        document = (DOCS / name).read_text(encoding="utf-8")
        for target in markdown_link.findall(document):
            if "://" in target or target.startswith("#"):
                continue
            assert (
                ((DOCS / name).parent / target).resolve().is_file()
            ), f"broken local link in {name}: {target}"


def test_state_permission_audit_passes_private_tree_and_redacts_locations(tmp_path: Path) -> None:
    config = IrohServiceConfig.default("secure", state_root=tmp_path)
    layout = ensure_state_layout(config)
    secret_named_file = layout.data_dir / "customer-secret-filename"
    secret_named_file.write_bytes(b"content")
    secret_named_file.chmod(0o600)

    clean = audit_state_permissions(config)
    assert clean.passed

    secret_named_file.chmod(0o644)
    report = audit_state_permissions(config)
    assert not report.passed
    encoded = json.dumps(report.as_dict())
    assert "state.permissions" in encoded
    assert "customer-secret-filename" not in encoded
    assert stat.S_IMODE(secret_named_file.stat().st_mode) == 0o644

    secret_named_file.chmod(0o700)
    assert "state.permissions" in {
        finding.code for finding in audit_state_permissions(config).findings
    }


def test_state_permission_audit_rejects_symlinks_and_bounds_walk(tmp_path: Path) -> None:
    config = IrohServiceConfig.default("links", state_root=tmp_path)
    layout = ensure_state_layout(config)
    (layout.data_dir / "escape").symlink_to(tmp_path)
    report = audit_state_permissions(config)
    assert {finding.code for finding in report.findings} == {"state.symlink"}

    bounded = audit_state_permissions(config, max_entries=1)
    assert "state.entry-limit" in {finding.code for finding in bounded.findings}


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (b"ref=credential://iroh/prod/node-key", "credential-reference"),
        (b"ref=secretref:vault:namespace/writer", "secret-reference"),
        (b"Authorization: Bearer synthetic-token-value", "authorization"),
        (b"iroh-ticket=synthetic-ticket-value", "iroh-authority"),
        (b"GET /?ticket=synthetic-ticket-value", "secret-query"),
        (b"-----BEGIN PRIVATE KEY-----", "private-key"),
        (b"https://operator:synthetic-password@example.invalid", "url-userinfo"),
    ],
)
def test_log_scan_detects_without_reflecting_secret(payload: bytes, code: str) -> None:
    report = scan_log_bytes(b"prefix " + payload + b" suffix")
    encoded = json.dumps(report.as_dict())
    assert not report.passed
    assert f"log.secret.{code}" in encoded
    assert payload.decode("ascii") not in encoded
    assert "synthetic" not in encoded


def test_log_scan_is_bounded_and_rejects_links(tmp_path: Path) -> None:
    log = tmp_path / "service.log"
    log.write_bytes(b"ordinary health message\n")
    assert scan_log(log).passed
    assert not scan_log(log, max_bytes=4).passed
    link = tmp_path / "link.log"
    link.symlink_to(log)
    assert {finding.code for finding in scan_log(link).findings} == {"log.unavailable"}


def test_client_redaction_removes_peer_and_authority_fields() -> None:
    result = redact(
        {
            "peer_id": "synthetic-peer",
            "ticket": "synthetic-ticket",
            "nested": {"authorization": "Bearer synthetic-token"},
        }
    )
    assert result == {
        "peer_id": REDACTED,
        "ticket": REDACTED,
        "nested": {"authorization": REDACTED},
    }


def test_ticket_and_manifest_attack_vectors_fail_closed() -> None:
    with pytest.raises(GovernedOperationError, match="malformed"):
        validate_ticket("ticket\nsecond-frame")
    with pytest.raises(GovernedOperationError):
        validate_ticket("x" * (MAX_TICKET_BYTES + 1))
    for path in ("../escape", "/absolute", "a//b", "a\\b", "a\x00b"):
        with pytest.raises(IrohInvalidPathError):
            validate_manifest_path(path)


def test_resource_limits_reject_absurd_values_and_audit_direct_instances(tmp_path: Path) -> None:
    document = IrohServiceConfig.default(state_root=tmp_path).to_dict()
    document["resources"]["max_connections"] = RESOURCE_LIMIT_MAXIMUMS["max_connections"] + 1
    with pytest.raises(IrohInvalidConfigError, match="max_connections"):
        IrohServiceConfig.from_dict(document)

    unsafe = ResourceLimits(
        max_concurrent_transfers=RESOURCE_LIMIT_MAXIMUMS["max_concurrent_transfers"] + 1
    )
    report = audit_resource_limits(unsafe)
    assert not report.passed
    assert {finding.code for finding in report.findings} == {"resource.above-maximum"}


def test_pinned_dependency_provenance_and_license_audit_fails_on_mutation() -> None:
    release = load_release_manifest(RELEASE)
    assert audit_release_manifest(release).passed

    checksum = copy.deepcopy(release)
    checksum["components"][0]["checksum_sha256"] = "not-a-checksum"
    assert "supply-chain.checksum" in {
        finding.code for finding in audit_release_manifest(checksum).findings
    }

    license_change = copy.deepcopy(release)
    license_change["components"][0]["license"] = "Unreviewed-1.0"
    assert "license.disallowed" in {
        finding.code for finding in audit_release_manifest(license_change).findings
    }

    provenance = copy.deepcopy(release)
    provenance["verification"]["sidecar_artifacts"]["attestation"]["required"] = False
    assert "supply-chain.provenance" in {
        finding.code for finding in audit_release_manifest(provenance).findings
    }


def test_archive_expansion_is_bounded_before_output_is_installed(tmp_path: Path) -> None:
    archive = tmp_path / "bomb.tar.gz"
    payload = b"\0" * (4 * 1024 * 1024)
    with tarfile.open(archive, "w:gz") as bundle:
        member = tarfile.TarInfo("bundle/ipfs-kit-iroh-sidecar")
        member.size = len(payload)
        member.mode = 0o755
        bundle.addfile(member, io.BytesIO(payload))
    output = tmp_path / "sidecar"
    installer = IrohInstaller(release_manifest=load_release_manifest(RELEASE))
    with pytest.raises(UnsafeArchiveError, match="compression ratio"):
        installer._extract_executable(
            archive,
            {"executable": "ipfs-kit-iroh-sidecar", "archive_format": "tar.gz"},
            output,
        )
    assert not output.exists()


def test_combined_security_audit_receipt_is_safe_and_complete(tmp_path: Path) -> None:
    config = IrohServiceConfig.default("audit", state_root=tmp_path)
    ensure_state_layout(config)
    log = config.layout.service_log_path
    log.write_text("ready\n", encoding="utf-8")
    log.chmod(0o600)
    report = run_security_audit(config, release_manifest=RELEASE, logs=[log])
    assert report.passed
    receipt = report.as_dict()
    assert receipt["kind"] == SECURITY_REPORT_KIND
    assert set(receipt["checks"]) == {
        "state-permissions",
        "resource-limits",
        "dependency-pins",
        "license-policy",
        "provenance-policy",
        "log-redaction",
    }
    assert receipt["summary"]["finding_count"] == 0

    combined = combine_security_reports(report, scan_log_bytes(b"iroh-ticket=synthetic"))
    assert not combined.passed
    assert "synthetic" not in json.dumps(combined.as_dict())

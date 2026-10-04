"""Offline security gates for the managed Iroh backend.

The checks in this module are deliberately deterministic and side-effect free.
They are suitable for startup preflight, release CI, and incident collection:
no check resolves a credential, contacts a peer, or includes matched secret
material in its result.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

from .config import (
    DIRECTORY_MODE,
    FILE_MODE,
    RESOURCE_LIMIT_MAXIMUMS,
    IrohServiceConfig,
    IrohStateLayout,
    ResourceLimits,
)

SECURITY_REPORT_SCHEMA_VERSION = 1
SECURITY_REPORT_KIND = "ipfs-kit-iroh-security-report"
DEFAULT_MAX_LOG_BYTES = 16 * 1024 * 1024
DEFAULT_MAX_STATE_ENTRIES = 100_000

_EXPECTED_BUNDLE = "iroh-1.0.2-ipfs-kit.1"
_EXPECTED_COMPONENTS = {
    "iroh": "1.0.2",
    "iroh-blobs": "0.103.0",
    "iroh-docs": "0.101.0",
    "iroh-gossip": "0.101.0",
}
_ALLOWED_LICENSES = frozenset({"MIT OR Apache-2.0", "MIT/Apache-2.0"})
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_HEX_40 = re.compile(r"^[0-9a-f]{40}$")

# Patterns operate on bytes so arbitrary/binary logs never need decoding.  A
# finding contains only the rule identifier and byte offset, never the match.
_LOG_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[bytes]], ...] = (
    ("credential-reference", re.compile(rb"(?i)credential://iroh/[a-z0-9._/-]+")),
    ("secret-reference", re.compile(rb"(?i)secretref:[a-z0-9._-]+:[a-z0-9._/-]+")),
    ("authorization", re.compile(rb"(?i)\b(?:bearer|token)\s+[a-z0-9._~+\-/=]{8,}")),
    (
        "iroh-authority",
        re.compile(
            rb"(?i)\biroh[-_](?:doc[-_])?(?:ticket|capability|private[-_]?key)"
            rb"[=:\s]+[^\s,;]{4,}"
        ),
    ),
    (
        "secret-query",
        re.compile(rb"(?i)[?&](?:token|ticket|secret|password|credential|capability)=[^&#\s]+"),
    ),
    ("private-key", re.compile(rb"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")),
    ("url-userinfo", re.compile(rb"(?i)\b[a-z][a-z0-9+.-]*://[^\s/@:]+:[^\s/@]*@")),
)


@dataclass(frozen=True, slots=True)
class SecurityFinding:
    """One non-secret security gate failure."""

    code: str
    severity: str
    location: str
    message: str
    remediation: str

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "location": self.location,
            "message": self.message,
            "remediation": self.remediation,
        }


@dataclass(frozen=True, slots=True)
class SecurityReport:
    """Stable security receipt safe to serialize to logs or CI artifacts."""

    checks: tuple[str, ...]
    findings: tuple[SecurityFinding, ...]

    @property
    def passed(self) -> bool:
        return not self.findings

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SECURITY_REPORT_SCHEMA_VERSION,
            "kind": SECURITY_REPORT_KIND,
            "passed": self.passed,
            "checks": list(self.checks),
            "summary": {
                "finding_count": len(self.findings),
                "critical": sum(item.severity == "critical" for item in self.findings),
                "high": sum(item.severity == "high" for item in self.findings),
                "medium": sum(item.severity == "medium" for item in self.findings),
                "low": sum(item.severity == "low" for item in self.findings),
            },
            "findings": [item.as_dict() for item in self.findings],
        }


def _finding(
    code: str,
    severity: str,
    location: str,
    message: str,
    remediation: str,
) -> SecurityFinding:
    return SecurityFinding(code, severity, location, message, remediation)


def _opaque_location(root: Path, path: Path) -> str:
    """Identify a state entry without exposing a user-controlled path."""

    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        relative = "outside-root"
    public = {
        ".": "state/root",
        "data": "state/data",
        "staging": "state/staging",
        "run": "state/run",
        "logs": "state/logs",
        "receipts": "state/receipts",
        "config.json": "state/config",
        ".instance.json": "state/owner-marker",
    }
    if relative in public:
        return public[relative]
    digest = hashlib.sha256(relative.encode("utf-8", "surrogateescape")).hexdigest()[:16]
    return f"state/entry-{digest}"


def audit_state_permissions(
    config: IrohServiceConfig | IrohStateLayout,
    *,
    max_entries: int = DEFAULT_MAX_STATE_ENTRIES,
) -> SecurityReport:
    """Audit a state tree without following links or publishing its paths."""

    if isinstance(max_entries, bool) or not isinstance(max_entries, int) or max_entries < 1:
        raise ValueError("max_entries must be a positive integer")
    layout = config.layout if isinstance(config, IrohServiceConfig) else config
    policy = config.ownership if isinstance(config, IrohServiceConfig) else None
    expected_uid = None if policy is None else policy.uid
    expected_gid = None if policy is None else policy.gid
    root = layout.root
    findings: list[SecurityFinding] = []

    current = Path(root.anchor)
    for component in root.parts[1:] if root.is_absolute() else root.parts:
        current /= component
        try:
            component_meta = current.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            findings.append(
                _finding(
                    "state.ancestor-unreadable",
                    "critical",
                    "state/root",
                    "A state path component cannot be inspected safely.",
                    "Stop the instance and restore an owner-controlled state path.",
                )
            )
            return SecurityReport(("state-permissions",), tuple(findings))
        if stat.S_ISLNK(component_meta.st_mode):
            findings.append(
                _finding(
                    "state.ancestor-symlink",
                    "critical",
                    "state/root",
                    "A state path component is a symbolic link.",
                    "Move the state tree to a real owner-controlled path before use.",
                )
            )
            return SecurityReport(("state-permissions",), tuple(findings))

    try:
        root_meta = root.lstat()
    except OSError:
        findings.append(
            _finding(
                "state.unavailable",
                "high",
                "state/root",
                "The Iroh state root cannot be inspected.",
                "Stop the instance and restore an owner-controlled state root.",
            )
        )
        return SecurityReport(("state-permissions",), tuple(findings))
    if not stat.S_ISDIR(root_meta.st_mode) or stat.S_ISLNK(root_meta.st_mode):
        findings.append(
            _finding(
                "state.invalid-root",
                "critical",
                "state/root",
                "The Iroh state root is not a real directory.",
                "Replace it with a private directory; never use a symlink or special file.",
            )
        )
        return SecurityReport(("state-permissions",), tuple(findings))

    pending = [root]
    visited = 0
    while pending:
        current = pending.pop()
        visited += 1
        if visited > max_entries:
            findings.append(
                _finding(
                    "state.entry-limit",
                    "high",
                    "state/root",
                    "The permission audit exceeded its bounded entry count.",
                    "Quiesce the instance, investigate unexpected file growth, and rerun with an approved bound.",
                )
            )
            break
        location = _opaque_location(root, current)
        try:
            metadata = current.lstat()
        except OSError:
            findings.append(
                _finding(
                    "state.entry-unreadable",
                    "high",
                    location,
                    "A state entry changed or became unreadable during audit.",
                    "Quiesce the instance and repeat the audit before use.",
                )
            )
            continue

        mode = metadata.st_mode
        if stat.S_ISLNK(mode):
            findings.append(
                _finding(
                    "state.symlink",
                    "critical",
                    location,
                    "A symbolic link exists in the Iroh state tree.",
                    "Stop the instance, remove the link, and restore verified data inside the state root.",
                )
            )
            continue
        if expected_uid is not None and metadata.st_uid != expected_uid:
            findings.append(
                _finding(
                    "state.owner",
                    "high",
                    location,
                    "A state entry has an unexpected owner.",
                    "Restore the configured service-account ownership while the instance is stopped.",
                )
            )
        if expected_gid is not None and metadata.st_gid != expected_gid:
            findings.append(
                _finding(
                    "state.group",
                    "high",
                    location,
                    "A state entry has an unexpected group.",
                    "Restore the configured service-account group while the instance is stopped.",
                )
            )

        permissions = stat.S_IMODE(mode)
        expected = DIRECTORY_MODE if stat.S_ISDIR(mode) else FILE_MODE
        if permissions & ~expected:
            findings.append(
                _finding(
                    "state.permissions",
                    "high",
                    location,
                    "A state entry has permission bits outside the approved owner-only mode.",
                    f"Set owner-only permissions no broader than {expected:04o}.",
                )
            )

        if stat.S_ISDIR(mode):
            try:
                with os.scandir(current) as entries:
                    pending.extend(Path(entry.path) for entry in entries)
            except OSError:
                findings.append(
                    _finding(
                        "state.directory-unreadable",
                        "high",
                        location,
                        "A state directory cannot be enumerated safely.",
                        "Quiesce the instance and restore service-account access before use.",
                    )
                )
        elif not (stat.S_ISREG(mode) or stat.S_ISSOCK(mode)):
            findings.append(
                _finding(
                    "state.special-file",
                    "critical",
                    location,
                    "An unsupported special file exists in the Iroh state tree.",
                    "Remove device, FIFO, and other special files before restarting the instance.",
                )
            )

    return SecurityReport(("state-permissions",), tuple(findings))


def _scan_stream(stream: BinaryIO, *, max_bytes: int) -> list[SecurityFinding]:
    findings: list[SecurityFinding] = []
    seen_rules: set[str] = set()
    consumed = 0
    overlap = b""
    chunk_size = 64 * 1024
    while consumed < max_bytes:
        chunk = stream.read(min(chunk_size, max_bytes - consumed))
        if not chunk:
            break
        consumed += len(chunk)
        payload = overlap + chunk
        base_offset = consumed - len(chunk) - len(overlap)
        for rule, pattern in _LOG_SECRET_PATTERNS:
            if rule in seen_rules:
                continue
            match = pattern.search(payload)
            if match is not None:
                seen_rules.add(rule)
                findings.append(
                    _finding(
                        f"log.secret.{rule}",
                        "critical",
                        f"log/byte-{max(0, base_offset + match.start())}",
                        "Potential credential material appears in diagnostic output.",
                        "Restrict the artifact, rotate the affected authority, purge it under retention policy, and fix redaction.",
                    )
                )
        overlap = payload[-4096:]
    if stream.read(1):
        findings.append(
            _finding(
                "log.scan-limit",
                "high",
                "log",
                "The log exceeds the approved bounded scan size.",
                "Scan the complete artifact with an approved offline scanner before release or disclosure.",
            )
        )
    return findings


def scan_log(
    path: str | os.PathLike[str], *, max_bytes: int = DEFAULT_MAX_LOG_BYTES
) -> SecurityReport:
    """Scan one regular, non-symlink log without returning matched bytes."""

    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
        raise ValueError("max_bytes must be a positive integer")
    target = Path(path)
    descriptor: int | None = None
    try:
        metadata = target.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise OSError("not a regular file")
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(target, flags)
        descriptor_meta = os.fstat(descriptor)
        if not stat.S_ISREG(descriptor_meta.st_mode):
            raise OSError("not a regular file")
        stream = os.fdopen(descriptor, "rb")
        descriptor = None
        with stream:
            findings = _scan_stream(stream, max_bytes=max_bytes)
    except OSError:
        findings = [
            _finding(
                "log.unavailable",
                "high",
                "log",
                "The requested log is unavailable or is not a regular file.",
                "Provide an owner-controlled regular file and repeat the scan.",
            )
        ]
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return SecurityReport(("log-redaction",), tuple(findings))


def scan_log_bytes(payload: bytes, *, max_bytes: int = DEFAULT_MAX_LOG_BYTES) -> SecurityReport:
    """In-memory variant used by support-bundle and conformance tooling."""

    import io

    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
        raise ValueError("max_bytes must be a positive integer")
    return SecurityReport(
        ("log-redaction",), tuple(_scan_stream(io.BytesIO(payload), max_bytes=max_bytes))
    )


def audit_resource_limits(
    resources: ResourceLimits | Mapping[str, Any],
) -> SecurityReport:
    """Verify runtime limits remain inside the product's tested safety envelope."""

    try:
        limits = (
            resources
            if isinstance(resources, ResourceLimits)
            else ResourceLimits.from_dict(resources)
        )
    except Exception as exc:
        # IrohInvalidConfigError is intentionally not reflected; configuration
        # exceptions may include caller-controlled field names.
        del exc
        return SecurityReport(
            ("resource-limits",),
            (
                _finding(
                    "resource.invalid",
                    "high",
                    "config/resources",
                    "The Iroh resource policy is invalid.",
                    "Replace it with a schema-valid, bounded resource policy.",
                ),
            ),
        )
    findings: list[SecurityFinding] = []
    values = limits.to_dict()
    for name, maximum in RESOURCE_LIMIT_MAXIMUMS.items():
        if values[name] > maximum:
            findings.append(
                _finding(
                    "resource.above-maximum",
                    "high",
                    f"config/resources/{name}",
                    "A resource limit exceeds the tested safety envelope.",
                    f"Set {name} to no more than {maximum} and use an OS limit as a second boundary.",
                )
            )
    if limits.max_staging_bytes > limits.max_storage_bytes:
        findings.append(
            _finding(
                "resource.staging-exceeds-storage",
                "high",
                "config/resources/max_staging_bytes",
                "Staging capacity exceeds total storage capacity.",
                "Set staging capacity no higher than total storage capacity.",
            )
        )
    return SecurityReport(("resource-limits",), tuple(findings))


def _release_finding(code: str, location: str, message: str) -> SecurityFinding:
    return _finding(
        code,
        "critical",
        location,
        message,
        "Reject the bundle; regenerate the audited pin set and rerun supply-chain review.",
    )


def audit_release_manifest(
    release: Mapping[str, Any] | str | os.PathLike[str],
) -> SecurityReport:
    """Audit pinned versions, provenance policy, checksums, and licenses offline."""

    if isinstance(release, (str, os.PathLike)):
        try:
            with Path(release).open("r", encoding="utf-8") as stream:
                value = json.load(stream)
        except (OSError, UnicodeError, json.JSONDecodeError):
            value = None
    else:
        value = release
    if not isinstance(value, Mapping):
        return SecurityReport(
            ("dependency-pins", "license-policy", "provenance-policy"),
            (
                _release_finding(
                    "supply-chain.invalid-manifest",
                    "release",
                    "The release manifest is unavailable or invalid.",
                ),
            ),
        )

    findings: list[SecurityFinding] = []
    bundle = value.get("release_bundle")
    if (
        not isinstance(bundle, Mapping)
        or bundle.get("id") != _EXPECTED_BUNDLE
        or bundle.get("status") != "supported"
    ):
        findings.append(
            _release_finding(
                "supply-chain.bundle",
                "release/bundle",
                "The selected release bundle is not the audited bundle.",
            )
        )

    raw_components = value.get("components")
    components: dict[str, Mapping[str, Any]] = {}
    if isinstance(raw_components, Sequence) and not isinstance(raw_components, (str, bytes)):
        for item in raw_components:
            if isinstance(item, Mapping) and isinstance(item.get("crate"), str):
                crate = str(item["crate"])
                if crate in components:
                    findings.append(
                        _release_finding(
                            "supply-chain.duplicate",
                            "release/components",
                            "The component pin set contains a duplicate crate.",
                        )
                    )
                components[crate] = item
    if set(components) != set(_EXPECTED_COMPONENTS):
        findings.append(
            _release_finding(
                "supply-chain.component-set",
                "release/components",
                "The component pin set is incomplete or contains an unreviewed crate.",
            )
        )
    for crate, expected_version in _EXPECTED_COMPONENTS.items():
        item = components.get(crate)
        if item is None:
            continue
        location = f"release/components/{crate}"
        if item.get("version") != expected_version:
            findings.append(
                _release_finding(
                    "supply-chain.version",
                    location,
                    "A component version differs from the audited pin.",
                )
            )
        if item.get("license") not in _ALLOWED_LICENSES:
            findings.append(
                _release_finding(
                    "license.disallowed",
                    location,
                    "A component license is absent or outside the approved policy.",
                )
            )
        checksum = item.get("checksum_sha256")
        if not isinstance(checksum, str) or _HEX_64.fullmatch(checksum) is None:
            findings.append(
                _release_finding(
                    "supply-chain.checksum", location, "A crate checksum is absent or malformed."
                )
            )
        commit = item.get("commit")
        if not isinstance(commit, str) or _HEX_40.fullmatch(commit) is None:
            findings.append(
                _release_finding(
                    "supply-chain.commit", location, "A source commit pin is absent or malformed."
                )
            )
        source = item.get("source")
        expected_source = f"https://crates.io/api/v1/crates/{crate}/{expected_version}/download"
        if source != expected_source:
            findings.append(
                _release_finding(
                    "supply-chain.source",
                    location,
                    "A crate source is not the exact approved crates.io archive.",
                )
            )
        features = item.get("features")
        if (
            not isinstance(features, list)
            or not features
            or any(not isinstance(feature, str) or not feature for feature in features)
        ):
            findings.append(
                _release_finding(
                    "supply-chain.features",
                    location,
                    "A component feature set is not explicitly pinned.",
                )
            )

    verification = value.get("verification")
    try:
        source_policy = verification["source_archives"]  # type: ignore[index]
        artifact_policy = verification["sidecar_artifacts"]  # type: ignore[index]
        attestation = artifact_policy["attestation"]
        provenance_ok = (
            verification.get("fail_closed") is True  # type: ignore[union-attr]
            and source_policy.get("algorithm") == "sha256"
            and source_policy.get("authority") == "crates.io"
            and source_policy.get("detached_signatures_available") is False
            and artifact_policy.get("algorithm") == "sha256"
            and artifact_policy.get("release_repository")
            == "https://github.com/endomorphosis/ipfs_kit_py"
            and attestation.get("required") is True
            and attestation.get("authority") == "github-artifact-attestations"
            and attestation.get("verification_command")
            == [
                "gh",
                "attestation",
                "verify",
                "{artifact}",
                "--repo",
                "endomorphosis/ipfs_kit_py",
            ]
        )
    except (AttributeError, KeyError, TypeError):
        provenance_ok = False
    if not provenance_ok:
        findings.append(
            _release_finding(
                "supply-chain.provenance",
                "release/verification",
                "Fail-closed checksum and attestation policy is not enabled.",
            )
        )

    sidecar = value.get("sidecar")
    if (
        not isinstance(sidecar, Mapping)
        or sidecar.get("binary") != "ipfs-kit-iroh-sidecar"
        or sidecar.get("version") != "0.1.0"
        or sidecar.get("owner") != "ipfs-kit"
    ):
        findings.append(
            _release_finding(
                "supply-chain.sidecar",
                "release/sidecar",
                "The sidecar identity or version differs from the audited build.",
            )
        )

    platforms = value.get("platforms")
    if not isinstance(platforms, list) or not platforms:
        findings.append(
            _release_finding(
                "supply-chain.platforms",
                "release/platforms",
                "The platform artifact matrix is absent.",
            )
        )
    else:
        platform_ids: set[str] = set()
        for platform in platforms:
            if not isinstance(platform, Mapping) or not isinstance(platform.get("id"), str):
                findings.append(
                    _release_finding(
                        "supply-chain.platform",
                        "release/platforms",
                        "A platform artifact record is malformed.",
                    )
                )
                continue
            identifier = str(platform["id"])
            if identifier in platform_ids:
                findings.append(
                    _release_finding(
                        "supply-chain.platform-duplicate",
                        "release/platforms",
                        "The platform matrix contains a duplicate target.",
                    )
                )
            platform_ids.add(identifier)
            if platform.get("installable") is True:
                digest = platform.get("checksum_sha256")
                size = platform.get("size")
                url = platform.get("url")
                if (
                    not isinstance(digest, str)
                    or _HEX_64.fullmatch(digest) is None
                    or isinstance(size, bool)
                    or not isinstance(size, int)
                    or size <= 0
                    or not isinstance(url, str)
                    or not url.startswith(
                        "https://github.com/endomorphosis/ipfs_kit_py/releases/download/"
                    )
                ):
                    findings.append(
                        _release_finding(
                            "supply-chain.artifact-pin",
                            "release/platforms",
                            "An installable artifact lacks an approved URL, size, or digest pin.",
                        )
                    )

    licenses = value.get("licenses")
    notice_files = licenses.get("upstream_notice_files") if isinstance(licenses, Mapping) else None
    if (
        not isinstance(licenses, Mapping)
        or licenses.get("spdx_expression") != "MIT OR Apache-2.0"
        or not isinstance(notice_files, list)
        or set(notice_files) != {"LICENSE-MIT", "LICENSE-APACHE"}
    ):
        findings.append(
            _release_finding(
                "license.notices",
                "release/licenses",
                "Required SPDX policy or redistribution notices are missing.",
            )
        )

    return SecurityReport(
        ("dependency-pins", "license-policy", "provenance-policy"), tuple(findings)
    )


def combine_security_reports(*reports: SecurityReport) -> SecurityReport:
    checks: list[str] = []
    findings: list[SecurityFinding] = []
    for report in reports:
        for check in report.checks:
            if check not in checks:
                checks.append(check)
        findings.extend(report.findings)
    return SecurityReport(tuple(checks), tuple(findings))


def run_security_audit(
    config: IrohServiceConfig,
    *,
    release_manifest: Mapping[str, Any] | str | os.PathLike[str],
    logs: Sequence[str | os.PathLike[str]] = (),
) -> SecurityReport:
    """Run all offline deployment gates and return one redacted receipt."""

    reports = [
        audit_state_permissions(config),
        audit_resource_limits(config.resources),
        audit_release_manifest(release_manifest),
    ]
    reports.extend(scan_log(path) for path in logs)
    return combine_security_reports(*reports)


__all__ = [
    "DEFAULT_MAX_LOG_BYTES",
    "DEFAULT_MAX_STATE_ENTRIES",
    "SECURITY_REPORT_KIND",
    "SECURITY_REPORT_SCHEMA_VERSION",
    "SecurityFinding",
    "SecurityReport",
    "audit_release_manifest",
    "audit_resource_limits",
    "audit_state_permissions",
    "combine_security_reports",
    "run_security_audit",
    "scan_log",
    "scan_log_bytes",
]

"""Offline conformance checks for the IROH-023 operator documentation."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "iroh"
DOCUMENTS = {
    name: DOCS / f"{name}.md" for name in ("operations", "security", "recovery")
}


def _read(name: str) -> str:
    return DOCUMENTS[name].read_text(encoding="utf-8")


def _compact(value: str) -> str:
    return " ".join(value.split())


def _section(document: str, heading: str) -> str:
    assert heading in document, f"missing heading: {heading}"
    value = document.split(heading, 1)[1]
    return value.split("\n## ", 1)[0]


def test_expected_runbooks_exist_and_identify_the_task_contract() -> None:
    for name, path in DOCUMENTS.items():
        assert path.is_file(), f"missing IROH-023 output: {path}"
        document = path.read_text(encoding="utf-8")
        assert document.startswith("# Iroh ")
        assert "Runbook: IROH-023" in document
        assert "iroh-1.0.2-ipfs-kit.1" in document
        assert "protocol 1" in document
        assert not re.search(r"\b(?:TODO|TBD|FIXME|PLACEHOLDER)\b", document, re.IGNORECASE)


def test_runbook_links_resolve_to_repository_files() -> None:
    markdown_link = re.compile(r"\[[^]]+\]\(([^)#]+)(?:#[^)]+)?\)")
    for name in DOCUMENTS:
        for target in markdown_link.findall(_read(name)):
            if "://" in target or target.startswith("#"):
                continue
            assert (DOCUMENTS[name].parent / target).resolve().is_file(), (
                f"broken local link in {name}.md: {target}"
            )


def test_operations_covers_deployment_upgrade_rollback_and_network_policy() -> None:
    document = _read("operations")
    for heading in (
        "## Deployment checklist",
        "## Install the verified sidecar",
        "## Configure a named instance",
        "## Network policy",
        "## Start and verify",
        "## Upgrade and rollback",
    ):
        assert heading in document
    for command in (
        "ipfs-kit-iroh install",
        "ipfs-kit-iroh inspect",
        "ipfs-kit-iroh update",
        "ipfs-kit-iroh rollback",
        "ipfs-kit-iroh-diagnostics",
    ):
        assert command in document
    compact = _compact(document)
    assert "`update --check` is read-only" in compact
    assert "The plain `update` performs the change" in compact
    network = _section(document, "## Network policy")
    for requirement in (
        "Local RPC",
        "Direct Iroh transport",
        "QUIC over UDP",
        "HTTPS relay",
        "DNS",
        "Local discovery",
        "never expose through a TCP proxy",
    ):
        assert requirement in network


def test_operations_covers_sharing_export_gc_and_lossless_uninstall() -> None:
    document = _read("operations")
    for heading in (
        "## Namespace sharing",
        "## Data export and IPFS synchronization",
        "## Garbage collection",
        "## Complete uninstall without data loss",
    ):
        assert heading in document
    compact = _compact(document).lower()
    for requirement in (
        "IrohBlobStore.export()",
        "cid` and `iroh_hash",
        "IrohGarbageCollector.collect(dry_run=True",
        "resume an interrupted live run",
        "provider-native export of the node identity",
        "Restore that bundle into an isolated test location",
        "Removing the binary does not remove state or credentials",
    ):
        assert requirement.lower() in compact


def test_security_covers_secret_handling_hardening_and_rotation() -> None:
    document = _read("security")
    for heading in (
        "## Trust boundaries and protected assets",
        "## Credential rules",
        "## Host and filesystem hardening",
        "## Network hardening",
        "## Safe namespace sharing",
        "## Key and capability rotation",
        "### Rotate the node identity",
        "### Rotate namespace capabilities and tickets",
        "## Logging, diagnostics, and audit",
        "## Backup security",
        "## Security incident procedure",
    ):
        assert heading in document
    compact = _compact(document)
    for requirement in (
        "Node private identity",
        "ticket or write capability is bearer authority",
        "Never run two nodes concurrently with the same restored private identity",
        "deleting a secret-store record revoked remote copies",
        "Encrypt in transit and at rest",
        "local RPC",
    ):
        assert requirement in compact


def test_recovery_defines_complete_backup_and_restore_procedures() -> None:
    document = _read("recovery")
    for heading in (
        "## Recovery objectives and ownership",
        "## Backup set",
        "## Backup procedure",
        "## Restore procedure",
        "## Recovery test and acceptance",
    ):
        assert heading in document
    backup = _section(document, "## Backup set")
    for requirement in (
        "data/",
        "Node identity credential",
        "Namespace write capabilities",
        "Canonical manifest snapshots",
        "GC reference-tracker DuckDB",
        "mappings.json",
        "checkpoints/",
        "receipts.jsonl",
        "run/` socket, service lock, and PID receipt | No",
    ):
        assert requirement in backup
    compact = _compact(document)
    assert "Never restore over a running instance" in compact
    assert "Verify the signed/MACed backup inventory and every file digest" in compact
    assert "Do not run live GC until reconciliation" in compact


def test_recovery_covers_outages_integrity_repair_and_disasters() -> None:
    document = _read("recovery")
    for heading in (
        "## Outage modes",
        "## Recover a corrupt namespace head",
        "## Recover missing or corrupt blobs",
        "## Recover GC state",
        "## Recover synchronization",
        "## Recovery without the original node identity",
        "## Disaster scenarios",
        "### Total host loss",
        "### Region or relay loss",
        "### Malicious or accidental deletion",
        "### Failed upgrade",
    ):
        assert heading in document
    compact = _compact(document).lower()
    for requirement in (
        "IrohManifestStore.recover_head()",
        "dry_run=True",
        "ReferenceTracker.repair(manifests, blobs)",
        "newest unique verified chain",
        "do not merge by wall clock",
        "publish recovered content as a new successor revision",
    ):
        assert requirement.lower() in compact


def test_cross_runbook_safety_invariants_are_explicit() -> None:
    combined = _compact("\n".join(_read(name) for name in DOCUMENTS))
    for invariant in (
        "0700",
        "0600",
        "BLAKE3",
        "compare-and-swap",
        "read-only",
        "credential://iroh/",
        "secretref:",
        "Never relabel an Iroh hash as a CID",
        "An upgrade is not a backup",
        "A relay is not a backup",
        "Deleting a ticket reference only removes the local copy",
    ):
        assert invariant in combined

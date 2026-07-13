"""Offline conformance tests for the frozen IROH-003 capability matrix."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "iroh" / "capability-matrix.md"
CONTRACT_PATH = ROOT / "tests" / "fixtures" / "iroh" / "filesystem" / "contract-v1.json"

EXPECTED_CAPABILITIES = {
    "ls": "emulated",
    "info": "emulated",
    "open": "emulated",
    "ranged read": "native",
    "write": "emulated",
    "mkdir": "emulated",
    "rm": "emulated",
    "cp": "emulated",
    "mv": "emulated",
    "find": "emulated",
    "glob": "emulated",
    "exists": "emulated",
    "sync": "native",
}

EXPECTED_UNSUPPORTED = {
    "symbolic and hard links",
    "ownership and mode mutation",
    "timestamp and extended metadata mutation",
    "filesystem watches and notifications",
    "file locks and leases exposed as POSIX locks",
    "memory mapping, file descriptors, or local host-path exposure",
    "sparse files, reflinks, device nodes, sockets, and FIFOs",
    "append, random write, update mode, and truncate-existing",
    "atomic mutation spanning namespaces or backend instances",
    "implicit IPFS CID/Iroh hash conversion or backend fallback",
}

CAPABILITY_ROW = re.compile(
    r"^\| `(?P<operation>[^`]+)` \| "
    r"`(?P<classification>native|emulated|unsupported)` \|",
    re.MULTILINE,
)
UNSUPPORTED_ROW = re.compile(
    r"^\| (?P<capability>[^|`]+?)(?: \([^|]+\))? \| `unsupported` \|",
    re.MULTILINE,
)


def _document() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def _section(document: str, heading: str, next_heading: str) -> str:
    assert heading in document, f"missing heading: {heading}"
    section = document.split(heading, 1)[1]
    assert next_heading in section, f"missing heading after {heading}: {next_heading}"
    return section.split(next_heading, 1)[0]


def _compact(value: str) -> str:
    """Make prose assertions insensitive to Markdown source wrapping."""

    return " ".join(value.split())


def test_document_identifies_frozen_decision_and_dependency() -> None:
    document = _document()
    assert "Decision: IROH-003" in document
    assert "Status: frozen, version 1" in document
    assert "iroh-1.0.2-ipfs-kit.1" in document
    assert "[IROH-002](filesystem-contract.md)" in document


def test_classification_vocabulary_is_closed_and_fail_closed() -> None:
    section = _section(
        _document(),
        "## Classification vocabulary",
        "## Required operation capability matrix",
    )
    classifications = re.findall(
        r"^\| `(native|emulated|unsupported)` \|", section, re.MULTILINE
    )
    assert classifications == ["native", "emulated", "unsupported"]
    assert "IROH_UNSUPPORTED_OPERATION" in section
    assert "never process-local bookkeeping" in section
    assert "required, supported operations" in section


def test_required_capability_matrix_has_exact_operation_set_and_classes() -> None:
    section = _section(
        _document(),
        "## Required operation capability matrix",
        "### Common metadata shape",
    )
    rows = CAPABILITY_ROW.findall(section)
    assert len(rows) == len(EXPECTED_CAPABILITIES)
    assert len({operation for operation, _ in rows}) == len(rows)
    assert dict(rows) == EXPECTED_CAPABILITIES


def test_native_rows_name_the_pinned_sidecar_primitives() -> None:
    document = _document()
    for primitive in (
        "blobs.stat",
        "blobs.read_range",
        "sync.start",
        "sync.progress",
        "sync.cancel",
        "sync.status",
    ):
        assert f"`{primitive}`" in document
    assert "Stage privately" in document
    assert "compare-and-swap" in document
    assert "tombstones" in document


def test_metadata_shape_is_consistent_and_secret_free() -> None:
    section = _section(
        _document(),
        "### Common metadata shape",
        "## Open, read, and write conformance",
    )
    for field in (
        "name",
        "type",
        "size",
        "mtime",
        "mode",
        "blob_hash",
        "revision",
        "metadata",
    ):
        assert re.search(rf"^\| `{field}` \|", section, re.MULTILINE)
    for forbidden in (
        "local cache paths",
        "tickets",
        "credential references",
        "capability material",
    ):
        assert forbidden in section


def test_open_modes_and_range_boundaries_are_unambiguous() -> None:
    section = _section(
        _document(),
        "## Open, read, and write conformance",
        "## Namespace operation conformance",
    )
    for mode in ('"rb"', '"r"', '"wb"', '"w"', '"xb"', '"x"'):
        assert mode in section
    prose = _compact(section)
    assert "[start, end)" in prose
    assert "SEEK_SET" in section
    assert "SEEK_CUR" in section
    assert "SEEK_END" in section
    assert "append" in section
    assert "in-place overwrite" in section
    assert section.count("IROH_UNSUPPORTED_OPERATION") >= 2
    assert "Exceptions from `close` MUST be observable" in prose


def test_namespace_matrix_freezes_atomic_and_cross_namespace_boundaries() -> None:
    section = _section(
        _document(),
        "## Namespace operation conformance",
        "## Synchronization conformance",
    )
    for operation in ("ls", "info", "mkdir", "rm", "cp", "mv", "find", "glob", "exists"):
        assert f"`{operation}`" in section
    prose = _compact(section)
    assert "exactly one new manifest revision or none" in prose
    assert "cross-namespace `cp`" in section
    assert "cross-namespace `mv`" in section
    assert "not atomic across namespaces" in section
    assert "only when lookup raises `IROH_NOT_FOUND`" in section
    assert "every other error is propagated" in _document()
    assert "`iroh+blob://`" in section
    assert "`iroh+ticket://`" in section


def test_sync_matrix_forbids_local_fallback_and_last_writer_wins() -> None:
    section = _section(
        _document(),
        "## Synchronization conformance",
        "## Unsupported capability matrix",
    )
    for code in (
        "IROH_SYNC_FAILED",
        "IROH_TIMEOUT",
        "IROH_CANCELLED",
        "IROH_CONFLICT",
        "IROH_CONFIG_INVALID",
    ):
        assert f"`{code}`" in section
    assert "MUST NOT fall back" in section
    assert "never choose by wall clock, arrival order, or last-writer-wins" in section
    assert (
        "does not mean that every referenced file blob has been eagerly downloaded"
        in _compact(section)
    )


def test_unsupported_matrix_is_complete_and_deterministic() -> None:
    section = _section(
        _document(),
        "## Unsupported capability matrix",
        "## Stable typed failure matrix",
    )
    rows = {capability.strip() for capability in UNSUPPORTED_ROW.findall(section)}
    assert rows == EXPECTED_UNSUPPORTED
    assert "fail before side effects" in section
    assert "`NotImplementedError`" in section
    assert "MUST NOT inherit an `AbstractFileSystem` default" in section


def test_stable_failure_matrix_covers_frozen_error_vocabulary() -> None:
    document = _document()
    section = _section(
        document,
        "## Stable typed failure matrix",
        "## Synchronous and asynchronous conformance",
    )
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    expected_codes = set(contract["error_codes"])
    documented_codes = set(re.findall(r"`(IROH_[A-Z_]+)`", section))
    assert documented_codes == expected_codes
    assert "only `exists` translates" in section
    assert "return an empty result" in section
    assert "safe message" in section
    assert "redacted structured context" in _compact(section)


def test_sync_and_async_surfaces_have_identical_conformance() -> None:
    section = _section(
        _document(),
        "## Synchronous and asynchronous conformance",
        "## Conformance requirements",
    )
    for requirement in (
        "same classification, return shape, ordering, range boundaries",
        "same manifest commit point and atomicity boundary",
        "same stable error `code`, safe context, and redaction",
        "same configured deadline",
    ):
        assert requirement in section
    assert "MUST NOT call `asyncio.run` in an already-running event loop" in section
    assert "without starting the requested operation" in section


def test_conformance_checklist_covers_security_and_failure_edges() -> None:
    section = _document().split("## Conformance requirements", 1)[1]
    for requirement in (
        "deterministic ordering",
        "integrity failure",
        "close-time commit",
        "abandoned-staging cleanup",
        "non-atomic cross-namespace boundaries",
        "Every unsupported capability",
        "Sync and async parity",
        "Fail-closed behavior",
        "Redaction of raw tickets",
    ):
        assert requirement in section
    assert "python -m pytest -q tests/test_iroh_capability_matrix.py" in section

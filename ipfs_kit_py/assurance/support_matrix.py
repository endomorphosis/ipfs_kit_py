"""PCPR-027 authoritative Kit support matrix.

One current-head matrix classifies Kit surfaces with the closed vocabulary
hermetic_qualified, live_qualified, conditional, configuration_only,
experimental, unavailable, and unsupported. README claims must be generated
from or checked against this matrix.

Fail-closed invariants:

* live_qualified and live_support_claim require live evidence in this
  evaluation; hermetic or simulated results cannot mint them;
* missing environments stay typed unavailable, never zero or passing;
* presence of a binary, import, extra, or configuration pin is not support;
* this matrix never writes DuckDB or Quack state and never emits a closed
  PCPR release.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final

from ipfs_kit_py.assurance.interface_parity import (
    BACKEND_ID as INTERFACE_PARITY_ID,
    INTERFACE as INTERFACE_PARITY_INTERFACE,
    LIVE_SUPPORT_CLAIM as INTERFACE_PARITY_LIVE_CLAIM,
    SCHEMA as INTERFACE_PARITY_SCHEMA,
    SUPPORT_CLASS as INTERFACE_PARITY_CLASS,
)
from ipfs_kit_py.assurance.iroh import (
    BACKEND_ID as IROH_ID,
    INTERFACE as IROH_INTERFACE,
    LIVE_SUPPORT_CLAIM as IROH_LIVE_CLAIM,
    SCHEMA as IROH_SCHEMA,
    SUPPORT_CLASS as IROH_CLASS,
)
from ipfs_kit_py.assurance.local_durable import (
    BACKEND_ID as LOCAL_ID,
    INTERFACE as LOCAL_INTERFACE,
    LIVE_SUPPORT_CLAIM as LOCAL_LIVE_CLAIM,
    SCHEMA as LOCAL_SCHEMA,
    SUPPORT_CLASS as LOCAL_CLASS,
)
from ipfs_kit_py.assurance.pinned_ipfs import (
    BACKEND_ID as PINNED_IPFS_ID,
    INTERFACE as PINNED_IPFS_INTERFACE,
    LIVE_SUPPORT_CLAIM as PINNED_IPFS_LIVE_CLAIM,
    PINNED_DAEMON_DIGEST,
    PINNED_DAEMON_VERSION,
    SCHEMA as PINNED_IPFS_SCHEMA,
    SUPPORT_CLASS as PINNED_IPFS_CLASS,
)
from ipfs_kit_py.assurance.proof_seal import (
    BACKEND_ID as PROOF_SEAL_ID,
    INTERFACE as PROOF_SEAL_INTERFACE,
    LIVE_SUPPORT_CLAIM as PROOF_SEAL_LIVE_CLAIM,
    SCHEMA as PROOF_SEAL_SCHEMA,
    SUPPORT_CLASS as PROOF_SEAL_CLASS,
)
from ipfs_kit_py.assurance.sibling_test_tree import (
    BACKEND_ID as SIBLING_ID,
    INTERFACE as SIBLING_INTERFACE,
    LIVE_SUPPORT_CLAIM as SIBLING_LIVE_CLAIM,
    SCHEMA as SIBLING_SCHEMA,
    SUPPORT_CLASS as SIBLING_CLASS,
)
from ipfs_kit_py.core.operation_contracts import content_identity


def _kit_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _literal_assignment(node: ast.AST) -> tuple[str, Any] | None:
    target = None
    value = None
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        target = node.targets[0]
        value = node.value
    elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        target = node.target
        value = node.value
    if not isinstance(target, ast.Name) or value is None:
        return None
    if isinstance(value, ast.Constant):
        return target.id, value.value
    return None


def _source_constants(relpath: str, names: tuple[str, ...]) -> dict[str, Any]:
    """Read module constants from source. Avoids importing anyio-bound VFS."""

    path = _kit_root() / relpath
    if not path.is_file():
        raise SupportMatrixError(f"{relpath} is absent; cannot classify that surface")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: dict[str, Any] = {}
    for node in tree.body:
        assignment = _literal_assignment(node)
        if assignment is None:
            continue
        name, value = assignment
        if name in names:
            found[name] = value
    missing = [name for name in names if name not in found]
    if missing:
        raise SupportMatrixError(
            f"{relpath} is missing required constants: {', '.join(missing)}"
        )
    return found


def vfs_wal_source_constants() -> dict[str, Any]:
    return _source_constants(
        "ipfs_kit_py/assurance/vfs_wal_recovery.py",
        ("BACKEND_ID", "INTERFACE", "SCHEMA", "SUPPORT_CLASS", "LIVE_SUPPORT_CLAIM"),
    )


INTERFACE: Final = "AuthoritativeSupportMatrix@1"
SCHEMA: Final = "ipfs_kit_py/assurance/support-matrix@1"
BACKEND_ID: Final = "support_matrix"
SUPPORT_CLASS: Final = "conditional"
LIVE_SUPPORT_CLAIM: Final = False
CERTIFICATION_SCOPE: Final = (
    "pcpr-027-authoritative-support-matrix; not a closed PCPR release"
)
POLICY: Final = "AuthoritativeSupportMatrixPolicy@1"
README_BEGIN_MARKER: Final = "<!-- pcpr-027-support-matrix:begin -->"
README_END_MARKER: Final = "<!-- pcpr-027-support-matrix:end -->"

SUPPORT_CLASSES: Final[tuple[str, ...]] = (
    "hermetic_qualified",
    "live_qualified",
    "conditional",
    "configuration_only",
    "experimental",
    "unavailable",
    "unsupported",
)
SUPPORT_CLASS_SET: Final[frozenset[str]] = frozenset(SUPPORT_CLASSES)

LIVE_CLASSES: Final[frozenset[str]] = frozenset({"live_qualified"})
HERMETIC_CLASSES: Final[frozenset[str]] = frozenset({"hermetic_qualified"})
NON_LIVE_CLASSES: Final[frozenset[str]] = frozenset(
    {
        "hermetic_qualified",
        "conditional",
        "configuration_only",
        "experimental",
        "unavailable",
        "unsupported",
    }
)


class SupportMatrixError(ValueError):
    """Malformed support-matrix row or a forbidden authority claim."""


@dataclass(frozen=True)
class SupportRow:
    """One current-head support-matrix row. Never a closed release."""

    surface_id: str
    display_name: str
    support_class: str
    live_support_claim: bool
    evidence_kind: str
    live: bool
    simulated: bool
    hermetic: bool
    producing_task: str
    schema: str
    interface: str
    reason: str
    limitations: tuple[str, ...] = ()
    details: Mapping[str, Any] = MappingProxyType({})

    def to_mapping(self) -> dict[str, Any]:
        if self.support_class not in SUPPORT_CLASS_SET:
            raise SupportMatrixError(
                f"{self.surface_id} support_class is not in the closed vocabulary"
            )
        if self.live_support_claim and not self.live:
            raise SupportMatrixError(
                f"{self.surface_id} live_support_claim requires live evidence"
            )
        if self.support_class in LIVE_CLASSES and not self.live:
            raise SupportMatrixError(
                f"{self.surface_id} live_qualified requires live evidence"
            )
        if self.simulated and self.live:
            raise SupportMatrixError(
                f"{self.surface_id} simulated results cannot be represented as live"
            )
        if self.hermetic and self.live:
            raise SupportMatrixError(
                f"{self.surface_id} hermetic results cannot be represented as live"
            )
        if self.live_support_claim and self.support_class in NON_LIVE_CLASSES:
            raise SupportMatrixError(
                f"{self.surface_id} cannot claim live support under {self.support_class}"
            )
        return {
            "surface_id": self.surface_id,
            "display_name": self.display_name,
            "support_class": self.support_class,
            "live_support_claim": self.live_support_claim,
            "evidence_kind": self.evidence_kind,
            "live": self.live,
            "simulated": self.simulated,
            "hermetic": self.hermetic,
            "producing_task": self.producing_task,
            "schema": self.schema,
            "interface": self.interface,
            "reason": self.reason,
            "limitations": list(self.limitations),
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class SupportMatrix:
    """Authoritative current-head Kit support matrix. Not a closed release."""

    schema: str
    interface: str
    backend_id: str
    support_class: str
    live_support_claim: bool
    policy: str
    certification_scope: str
    production_authorized: bool
    closed_vocabulary: tuple[str, ...]
    live_qualified_row_count: int
    rows: tuple[SupportRow, ...]
    matrix_cid: str

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "interface": self.interface,
            "backend_id": self.backend_id,
            "support_class": self.support_class,
            "live_support_claim": self.live_support_claim,
            "policy": self.policy,
            "certification_scope": self.certification_scope,
            "production_authorized": self.production_authorized,
            "closed_vocabulary": list(self.closed_vocabulary),
            "live_qualified_row_count": self.live_qualified_row_count,
            "rows": [row.to_mapping() for row in self.rows],
            "matrix_cid": self.matrix_cid,
        }


def refuse_simulated_as_live(adapter: Any) -> None:
    """Hermetic, simulated, or live-claiming adapters cannot mint live evidence."""

    live_provider = bool(getattr(adapter, "live_provider", False))
    hermetic = bool(getattr(adapter, "is_hermetic", True))
    simulated = bool(getattr(adapter, "simulated", False))
    live_claim = bool(getattr(adapter, "live_support_claim", False))
    if hermetic or simulated or not live_provider or live_claim:
        raise SupportMatrixError(
            "hermetic or simulated adapters cannot mint live support-matrix qualification"
        )
    if getattr(adapter, "backend_id", None) != BACKEND_ID:
        raise SupportMatrixError(
            "live support-matrix qualification requires backend_id='support_matrix'"
        )


def _row(
    *,
    surface_id: str,
    display_name: str,
    support_class: str,
    producing_task: str,
    schema: str,
    interface: str,
    reason: str,
    evidence_kind: str,
    live: bool = False,
    simulated: bool = False,
    hermetic: bool = False,
    live_support_claim: bool = False,
    limitations: Sequence[str] = (),
    details: Mapping[str, Any] | None = None,
) -> SupportRow:
    return SupportRow(
        surface_id=surface_id,
        display_name=display_name,
        support_class=support_class,
        live_support_claim=live_support_claim,
        evidence_kind=evidence_kind,
        live=live,
        simulated=simulated,
        hermetic=hermetic,
        producing_task=producing_task,
        schema=schema,
        interface=interface,
        reason=reason,
        limitations=tuple(limitations),
        details=MappingProxyType(dict(details or {})),
    )


def declared_support_rows() -> tuple[SupportRow, ...]:
    """Current-head declared rows. Live_qualified is admitted and unused."""

    vfs = vfs_wal_source_constants()
    vfs_id = str(vfs["BACKEND_ID"])
    vfs_interface = str(vfs["INTERFACE"])
    vfs_schema = str(vfs["SCHEMA"])
    vfs_class = str(vfs["SUPPORT_CLASS"])
    vfs_live_claim = bool(vfs["LIVE_SUPPORT_CLAIM"])
    return (
        _row(
            surface_id=LOCAL_ID,
            display_name="Local durable filesystem",
            support_class=LOCAL_CLASS,
            producing_task="PCPR-020",
            schema=LOCAL_SCHEMA,
            interface=LOCAL_INTERFACE,
            reason=(
                "PCPR-020 measured live local POSIX durability for an incomplete "
                "suite. Incomplete live evidence cannot mint live_qualified. "
                "This matrix does not re-claim that POSIX session as a closed "
                "release."
            ),
            evidence_kind="measured",
            hermetic=False,
            limitations=("suite_incomplete", "not_a_closed_release"),
            details={"live_support_claim_source": LOCAL_LIVE_CLAIM},
        ),
        _row(
            surface_id=PINNED_IPFS_ID,
            display_name="Pinned IPFS (Kubo) backend",
            support_class=PINNED_IPFS_CLASS,
            producing_task="PCPR-021",
            schema=PINNED_IPFS_SCHEMA,
            interface=PINNED_IPFS_INTERFACE,
            reason=(
                "No digest-bound Kubo daemon is present on the sealed validation "
                "PATH. Live pinned IPFS stays typed unavailable and is not "
                "recorded as zero or passing."
            ),
            evidence_kind="unavailable",
            limitations=("ipfs_unavailable", "daemon_not_provisioned"),
            details={"live_support_claim_source": PINNED_IPFS_LIVE_CLAIM},
        ),
        _row(
            surface_id="pinned_ipfs_daemon_pin",
            display_name="Pinned IPFS daemon identity pin",
            support_class="configuration_only",
            producing_task="PCPR-021",
            schema=PINNED_IPFS_SCHEMA,
            interface=PINNED_IPFS_INTERFACE,
            reason=(
                "PINNED_DAEMON_VERSION and PINNED_DAEMON_DIGEST are configuration "
                "claims, not live daemon identity. Configuration is not live "
                "qualification."
            ),
            evidence_kind="measured",
            limitations=("configuration_is_not_live",),
            details={
                "pinned_daemon_version": PINNED_DAEMON_VERSION,
                "pinned_daemon_digest": PINNED_DAEMON_DIGEST,
            },
        ),
        _row(
            surface_id=IROH_ID,
            display_name="Iroh sidecar backend",
            support_class=IROH_CLASS,
            producing_task="PCPR-022",
            schema=IROH_SCHEMA,
            interface=IROH_INTERFACE,
            reason=(
                "Iroh remains experimental. No digest-bound ipfs-kit-iroh-sidecar "
                "is present on the sealed validation PATH. Simulated sidecar "
                "results cannot mint live qualification."
            ),
            evidence_kind="unavailable",
            limitations=("sidecar_unavailable", "experimental_not_live"),
            details={"live_support_claim_source": IROH_LIVE_CLAIM},
        ),
        _row(
            surface_id=vfs_id,
            display_name="VFS/WAL/current-root recovery",
            support_class=vfs_class,
            producing_task="PCPR-023",
            schema=vfs_schema,
            interface=vfs_interface,
            reason=(
                "Hermetic WAL recovery, current-root CAS, and mount-lifecycle "
                "fixtures were measured. Hermetic results cannot mint live "
                "qualification."
            ),
            evidence_kind="measured_hermetic",
            hermetic=True,
            limitations=("hermetic_not_live",),
            details={"live_support_claim_source": vfs_live_claim},
        ),
        _row(
            surface_id="linux_fuse_live",
            display_name="Linux FUSE live mount",
            support_class="unavailable",
            producing_task="PCPR-023",
            schema=vfs_schema,
            interface=vfs_interface,
            reason=(
                "No live Linux FUSE mount was exercised in this evaluation. "
                "fusermount presence is not a live mount and is not recorded as "
                "passing."
            ),
            evidence_kind="unavailable",
            limitations=("live_mount_not_exercised", "presence_is_not_support"),
        ),
        _row(
            surface_id="windows_winfsp",
            display_name="Windows WinFsp live mount",
            support_class="unsupported",
            producing_task="PCPR-023",
            schema=vfs_schema,
            interface=vfs_interface,
            reason=(
                "This sealed validation host is not Windows. WinFsp is unsupported "
                "here, not silently skipped and not recorded as passing."
            ),
            evidence_kind="unavailable",
            limitations=("host_is_not_windows",),
        ),
        _row(
            surface_id="container_fuse",
            display_name="Container FUSE live mount",
            support_class="unavailable",
            producing_task="PCPR-023",
            schema=vfs_schema,
            interface=vfs_interface,
            reason=(
                "No container FUSE mount was exercised. Docker presence is not a "
                "live FUSE mount and cannot mint live qualification."
            ),
            evidence_kind="unavailable",
            limitations=("live_mount_not_exercised", "presence_is_not_support"),
        ),
        _row(
            surface_id=PROOF_SEAL_ID,
            display_name="Proof-seal store",
            support_class=PROOF_SEAL_CLASS,
            producing_task="PCPR-024",
            schema=PROOF_SEAL_SCHEMA,
            interface=PROOF_SEAL_INTERFACE,
            reason=(
                "Hermetic proof-seal persistence, candidate versus current "
                "separation, and WAL recovery were measured. Hermetic results "
                "cannot mint live qualification."
            ),
            evidence_kind="measured_hermetic",
            hermetic=True,
            limitations=("hermetic_not_live",),
            details={"live_support_claim_source": PROOF_SEAL_LIVE_CLAIM},
        ),
        _row(
            surface_id=SIBLING_ID,
            display_name="Installed-package sibling test-tree decoupling",
            support_class=SIBLING_CLASS,
            producing_task="PCPR-025",
            schema=SIBLING_SCHEMA,
            interface=SIBLING_INTERFACE,
            reason=(
                "Hermetic source probes show sitecustomize and harnesses no "
                "longer inject a sibling checkout. Hermetic decoupling cannot "
                "mint live qualification."
            ),
            evidence_kind="measured_hermetic",
            hermetic=True,
            limitations=("hermetic_not_live",),
            details={"live_support_claim_source": SIBLING_LIVE_CLAIM},
        ),
        _row(
            surface_id=INTERFACE_PARITY_ID,
            display_name="Python/CLI/MCP/MCP++ adapter parity",
            support_class=INTERFACE_PARITY_CLASS,
            producing_task="PCPR-026",
            schema=INTERFACE_PARITY_SCHEMA,
            interface=INTERFACE_PARITY_INTERFACE,
            reason=(
                "AllInterfaceParityPolicy@1 adapter sessions for local-durable "
                "put/get/digest/delete were measured. In-process adapters are not "
                "live MCP servers and cannot mint live_qualified."
            ),
            evidence_kind="measured",
            limitations=("adapter_not_live_server", "live_mcp_server_unavailable"),
            details={"live_support_claim_source": INTERFACE_PARITY_LIVE_CLAIM},
        ),
        _row(
            surface_id="live_mcp_server",
            display_name="Live MCP stdio/HTTP/P2P server",
            support_class="unavailable",
            producing_task="PCPR-026",
            schema=INTERFACE_PARITY_SCHEMA,
            interface=INTERFACE_PARITY_INTERFACE,
            reason=(
                "No live MCP stdio, HTTP, or P2P server process was started. "
                "In-process JSON-RPC fixtures are not live server sessions."
            ),
            evidence_kind="unavailable",
            limitations=("mcp_server_not_started",),
        ),
    )


def generate_authoritative_support_matrix() -> SupportMatrix:
    """Build the fail-closed current-head matrix. Not a closed release."""

    rows = declared_support_rows()
    mappings = [row.to_mapping() for row in rows]
    live_qualified = sum(1 for item in mappings if item["support_class"] == "live_qualified")
    live_claims = sum(1 for item in mappings if item["live_support_claim"] is True)
    if live_qualified:
        raise SupportMatrixError(
            "live_qualified rows require live evidence in this evaluation"
        )
    if live_claims:
        raise SupportMatrixError(
            "live_support_claim cannot be true without live evidence"
        )
    used = {item["support_class"] for item in mappings}
    if not used <= SUPPORT_CLASS_SET:
        raise SupportMatrixError("row used a class outside the closed vocabulary")
    if "live_qualified" not in SUPPORT_CLASS_SET:
        raise SupportMatrixError("closed vocabulary must admit live_qualified")
    body = {
        "schema": SCHEMA,
        "interface": INTERFACE,
        "backend_id": BACKEND_ID,
        "support_class": SUPPORT_CLASS,
        "live_support_claim": False,
        "policy": POLICY,
        "certification_scope": CERTIFICATION_SCOPE,
        "production_authorized": False,
        "closed_vocabulary": list(SUPPORT_CLASSES),
        "live_qualified_row_count": live_qualified,
        "rows": mappings,
    }
    cid = content_identity(body)
    return SupportMatrix(
        schema=SCHEMA,
        interface=INTERFACE,
        backend_id=BACKEND_ID,
        support_class=SUPPORT_CLASS,
        live_support_claim=False,
        policy=POLICY,
        certification_scope=CERTIFICATION_SCOPE,
        production_authorized=False,
        closed_vocabulary=SUPPORT_CLASSES,
        live_qualified_row_count=live_qualified,
        rows=rows,
        matrix_cid=cid,
    )


def matrix_contract() -> dict[str, Any]:
    matrix = generate_authoritative_support_matrix()
    payload = matrix.to_mapping()
    payload.update(
        {
            "is_hermetic": True,
            "live_provider": False,
            "simulated": False,
            "production_authorized": False,
        }
    )
    return payload


def render_readme_claims(matrix: SupportMatrix | None = None) -> str:
    """Deterministic README block generated from the matrix."""

    matrix = matrix or generate_authoritative_support_matrix()
    lines = [
        "Authoritative current-head Kit support matrix (PCPR-027). Closed vocabulary: "
        + ", ".join(f"`{item}`" for item in SUPPORT_CLASSES)
        + ". Live claims require live evidence. Missing environments stay typed "
        "unavailable. Simulated and hermetic results cannot mint live qualification. "
        f"Zero surfaces are `live_qualified` (count={matrix.live_qualified_row_count}). "
        "This matrix is R&D non-promoted and is not a closed PCPR release.",
        "",
        f"Matrix CID: `{matrix.matrix_cid}`",
        "",
        "| Surface | Class | Live claim | Evidence | Source |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in matrix.rows:
        live_claim = "false"
        lines.append(
            f"| `{row.surface_id}` | `{row.support_class}` | {live_claim} | "
            f"{row.evidence_kind} | {row.producing_task} |"
        )
    lines.append("")
    return "\n".join(lines)


def extract_readme_matrix_block(readme: str) -> str:
    begin = readme.find(README_BEGIN_MARKER)
    end = readme.find(README_END_MARKER)
    if begin < 0 or end < 0 or end <= begin:
        raise SupportMatrixError(
            "README is missing the PCPR-027 support-matrix markers"
        )
    inner = readme[begin + len(README_BEGIN_MARKER) : end]
    return inner.strip("\n") + "\n"


def check_readme_against_matrix(
    readme: str,
    matrix: SupportMatrix | None = None,
) -> dict[str, Any]:
    """README claims must match the generated matrix and must not over-claim."""

    matrix = matrix or generate_authoritative_support_matrix()
    expected = render_readme_claims(matrix)
    observed = extract_readme_matrix_block(readme)
    if observed != expected:
        raise SupportMatrixError(
            "README support-matrix block does not match the generated matrix"
        )
    lowered = readme.lower()
    if "release_candidate_qualified" in lowered:
        raise SupportMatrixError("README must not claim a closed PCPR release outcome")
    forbidden_live = (
        "this is a closed pcpr release",
        "live_qualified production",
        "production-authorized ipfs",
    )
    for phrase in forbidden_live:
        if phrase in lowered:
            raise SupportMatrixError(f"README contains forbidden live claim: {phrase}")
    for row in matrix.rows:
        if f"`{row.surface_id}`" not in observed:
            raise SupportMatrixError(
                f"README matrix block omitted surface {row.surface_id}"
            )
        if f"`{row.support_class}`" not in observed:
            raise SupportMatrixError(
                f"README matrix block omitted class {row.support_class}"
            )
    if "production ready" in lowered:
        raise SupportMatrixError(
            "README still claims production ready; that contradicts the matrix"
        )
    return {
        "agrees": True,
        "matrix_cid": matrix.matrix_cid,
        "row_count": len(matrix.rows),
        "live_qualified_row_count": matrix.live_qualified_row_count,
        "live_support_claim": False,
    }


__all__ = [
    "INTERFACE",
    "SCHEMA",
    "BACKEND_ID",
    "SUPPORT_CLASS",
    "LIVE_SUPPORT_CLAIM",
    "CERTIFICATION_SCOPE",
    "POLICY",
    "README_BEGIN_MARKER",
    "README_END_MARKER",
    "SUPPORT_CLASSES",
    "SUPPORT_CLASS_SET",
    "SupportMatrixError",
    "SupportRow",
    "SupportMatrix",
    "refuse_simulated_as_live",
    "declared_support_rows",
    "vfs_wal_source_constants",
    "generate_authoritative_support_matrix",
    "matrix_contract",
    "render_readme_claims",
    "extract_readme_matrix_block",
    "check_readme_against_matrix",
]

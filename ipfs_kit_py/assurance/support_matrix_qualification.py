"""Fail-closed PCPR-027 authoritative support-matrix qualification.

PCPR-027 generates one current-head Kit support matrix using the closed
vocabulary hermetic_qualified, live_qualified, conditional,
configuration_only, experimental, unavailable, and unsupported. README
claims are generated from and checked against that matrix. Live claims
require live evidence. Missing environments stay typed unavailable.
Simulated and hermetic results cannot mint live qualification.

This module is not release authority: it does not write DuckDB or Quack
state and never emits a closed PCPR release outcome.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

from ipfs_kit_py.assurance.backend_certification import CertificationDisposition
from ipfs_kit_py.assurance.local_backend_qualification import (
    CLOSED_RELEASE_OUTCOMES,
    EVIDENCE_KINDS,
    PROMOTION_STATUSES,
    SEALED_PATH,
    QualificationProbe,
    observe_sealed_validation_environment,
)
from ipfs_kit_py.assurance.support_matrix import (
    BACKEND_ID,
    CERTIFICATION_SCOPE,
    INTERFACE as ADAPTER_INTERFACE,
    LIVE_SUPPORT_CLAIM,
    POLICY,
    SCHEMA as ADAPTER_SCHEMA,
    SUPPORT_CLASS,
    SUPPORT_CLASSES,
    SupportMatrix,
    SupportMatrixError,
    check_readme_against_matrix,
    generate_authoritative_support_matrix,
    matrix_contract,
    refuse_simulated_as_live,
    render_readme_claims,
)
from ipfs_kit_py.core.operation_contracts import content_identity


QUALIFICATION_INTERFACE: Final = "SupportMatrixQualification@1"
QUALIFICATION_SCHEMA: Final = (
    "ipfs_kit_py/assurance/support-matrix-qualification@1"
)
QUALIFICATION_VERDICT_SCHEMA: Final = (
    "ipfs_kit_py/assurance/support-matrix-qualification-verdict@1"
)

PCPR_027_TASK_ID: Final = "PCPR-027"
PCPR_027_GOAL_ID: Final = "PCPR-G300"
PCPR_026_TASK_ID: Final = "PCPR-026"
PCPR_PROGRAM_ID: Final = "proof-carrying-platform-qualification-and-release-v1"
PCPR_BOARD_NAMESPACE: Final = "proof-carrying-platform-qualification-and-release-v1"

HERMETIC_CANDIDATE_SUITES: Final[tuple[str, ...]] = (
    "tests/test_pcpr_support_matrix_qualification.py",
)

REQUIRED_MATRIX_OPERATIONS: Final[tuple[str, ...]] = (
    "closed_vocabulary_admitted",
    "every_row_uses_closed_class",
    "live_qualified_requires_live_evidence",
    "hermetic_not_represented_as_live",
    "simulated_not_represented_as_live",
    "readme_claims_agree",
    "missing_environments_typed_unavailable",
    "zero_live_qualified_surfaces",
)

LIVE_UNAVAILABLE_OPERATIONS: Final[tuple[str, ...]] = (
    "live_ipfs_transport",
    "live_iroh_sidecar",
    "live_linux_fuse_mount",
    "live_mcp_server",
)


class SupportMatrixQualificationError(ValueError):
    """Malformed qualification evidence or a forbidden authority claim."""


@dataclass(frozen=True)
class QualificationVerdict:
    """Fail-closed PCPR-027 support-matrix decision. Never a closed release."""

    schema: str
    interface: str
    promotion_status: str
    supervisor_disposition: str
    closed_release_outcome: None
    release_claim: bool
    completion_authoritative: bool
    contracts_frozen: bool
    duckdb_or_quack_state_written: bool
    support_matrix_live_qualified: bool
    suite_complete: bool
    certification_disposition: str
    support_class: str
    live_support_claim: bool
    simulated_results_represented_as_live: bool
    hermetic_results_represented_as_live: bool
    support_matrix_generated: bool
    readme_claims_agree: bool
    live_qualified_row_count: int
    live_ipfs_transport_qualified: bool
    live_ipfs_evidence_kind: str
    this_task_created_competing_authority: bool
    matrix_cid: str
    probes: tuple[QualificationProbe, ...]
    observations: tuple[dict[str, Any], ...]
    hermetic_operations: tuple[dict[str, Any], ...]
    live_unavailable_operations: tuple[dict[str, Any], ...]
    operations_observed: tuple[str, ...]
    operations_missing: tuple[str, ...]
    blockers: tuple[str, ...]
    verdict_cid: str

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "interface": self.interface,
            "promotion_status": self.promotion_status,
            "supervisor_disposition": self.supervisor_disposition,
            "closed_release_outcome": self.closed_release_outcome,
            "release_claim": self.release_claim,
            "completion_authoritative": self.completion_authoritative,
            "contracts_frozen": self.contracts_frozen,
            "duckdb_or_quack_state_written": self.duckdb_or_quack_state_written,
            "support_matrix_live_qualified": self.support_matrix_live_qualified,
            "suite_complete": self.suite_complete,
            "certification_disposition": self.certification_disposition,
            "support_class": self.support_class,
            "live_support_claim": self.live_support_claim,
            "simulated_results_represented_as_live": (
                self.simulated_results_represented_as_live
            ),
            "hermetic_results_represented_as_live": (
                self.hermetic_results_represented_as_live
            ),
            "support_matrix_generated": self.support_matrix_generated,
            "readme_claims_agree": self.readme_claims_agree,
            "live_qualified_row_count": self.live_qualified_row_count,
            "live_ipfs_transport_qualified": self.live_ipfs_transport_qualified,
            "live_ipfs_evidence_kind": self.live_ipfs_evidence_kind,
            "this_task_created_competing_authority": (
                self.this_task_created_competing_authority
            ),
            "matrix_cid": self.matrix_cid,
            "probes": [item.to_mapping() for item in self.probes],
            "observations": [dict(item) for item in self.observations],
            "hermetic_operations": [dict(item) for item in self.hermetic_operations],
            "live_unavailable_operations": [
                dict(item) for item in self.live_unavailable_operations
            ],
            "operations_observed": list(self.operations_observed),
            "operations_missing": list(self.operations_missing),
            "blockers": list(self.blockers),
            "verdict_cid": self.verdict_cid,
        }


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SupportMatrixQualificationError(f"{name} must be a non-empty string")
    return value.strip()


def _kind(value: Any, name: str) -> str:
    kind = _text(value, name)
    if kind not in EVIDENCE_KINDS:
        raise SupportMatrixQualificationError(
            f"{name} is not an admitted evidence kind"
        )
    return kind


def _reject_closed_release_value(value: Any, name: str) -> None:
    if isinstance(value, str) and value in CLOSED_RELEASE_OUTCOMES:
        raise SupportMatrixQualificationError(
            f"{name} must not be a closed PCPR release outcome"
        )


def _passed(
    operation: str,
    *,
    detail: str,
    digests: Mapping[str, str] | None = None,
    limitations: tuple[str, ...] = ("hermetic_not_live",),
) -> dict[str, Any]:
    return {
        "operation": operation,
        "status": "passed",
        "environment": "hermetic",
        "source": "hermetic_observed",
        "signature_valid": True,
        "freshness": "current",
        "digests": dict(digests or {}),
        "limitations": list(limitations),
        "detail": detail,
        "evidence_kind": "measured_hermetic",
        "live": False,
        "simulated_represented_as_live": False,
        "hermetic_represented_as_live": False,
    }


def _blocked(
    operation: str,
    *,
    reason: str,
    limitations: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "operation": operation,
        "status": "blocked",
        "environment": "live",
        "source": "unavailable",
        "signature_valid": False,
        "freshness": "missing",
        "digests": {"reason": reason},
        "limitations": list(limitations),
        "detail": reason,
        "evidence_kind": "unavailable",
        "live": False,
        "simulated_represented_as_live": False,
        "hermetic_represented_as_live": False,
    }


def _hermetic_operation(
    operation: str,
    *,
    status: str,
    reason: str,
    digests: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "operation": operation,
        "status": status,
        "environment": "hermetic",
        "source": "hermetic_observed",
        "evidence_kind": "measured_hermetic",
        "live": False,
        "simulated_represented_as_live": False,
        "hermetic_represented_as_live": False,
        "reason": reason,
        "digests": dict(digests or {}),
    }


def _live_unavailable_operation(operation: str, *, reason: str) -> dict[str, Any]:
    return {
        "operation": operation,
        "status": "unobserved",
        "environment": "sealed",
        "source": "unavailable",
        "evidence_kind": "unavailable",
        "live": False,
        "simulated_represented_as_live": False,
        "hermetic_represented_as_live": False,
        "reason": reason,
    }


def sealed_which(name: str) -> str:
    for directory in SEALED_PATH.split(":"):
        candidate = Path(directory) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return "unavailable"


def _kit_root() -> Path:
    return Path(__file__).resolve().parents[2]


def probe_live_ipfs_transport() -> QualificationProbe:
    ipfs = sealed_which("ipfs")
    present = ipfs != "unavailable"
    return QualificationProbe(
        probe_id="live_ipfs_transport",
        present=present,
        evidence_kind="measured" if present else "unavailable",
        live=False,
        simulated_represented_as_live=False,
        reason=(
            "Sealed PATH has an ipfs executable. This qualifier did not start a "
            "pinned daemon. Live IPFS stays typed unavailable."
            if present
            else (
                "Sealed PATH has no ipfs executable. Live IPFS stays typed "
                "unavailable and is not recorded as zero or passing. Support-"
                "matrix generation is not live IPFS."
            )
        ),
        details={
            "ipfs": ipfs,
            "PATH": SEALED_PATH,
            "live_daemon_started": False,
            "injected_transport_is_not_live": True,
        },
    )


def probe_live_iroh_sidecar() -> QualificationProbe:
    sidecar = sealed_which("ipfs-kit-iroh-sidecar")
    upstream = sealed_which("iroh")
    present = sidecar != "unavailable"
    return QualificationProbe(
        probe_id="live_iroh_sidecar",
        present=present,
        evidence_kind="measured" if present else "unavailable",
        live=False,
        simulated_represented_as_live=False,
        reason=(
            "Sealed PATH has ipfs-kit-iroh-sidecar. This qualifier did not start "
            "it. Live Iroh stays typed unavailable."
            if present
            else (
                "Sealed PATH has no ipfs-kit-iroh-sidecar. Iroh remains "
                "experimental and typed unavailable as live support."
            )
        ),
        details={
            "ipfs-kit-iroh-sidecar": sidecar,
            "iroh": upstream,
            "PATH": SEALED_PATH,
            "live_sidecar_started": False,
            "support_class": "experimental",
        },
    )


def probe_live_linux_fuse_mount() -> QualificationProbe:
    fusermount = sealed_which("fusermount")
    fusermount3 = sealed_which("fusermount3")
    dev_fuse = "/dev/fuse" if Path("/dev/fuse").exists() else "unavailable"
    return QualificationProbe(
        probe_id="live_linux_fuse_mount",
        present=False,
        evidence_kind="unavailable",
        live=False,
        simulated_represented_as_live=False,
        reason=(
            "No live Linux FUSE mount was exercised. fusermount or /dev/fuse "
            "presence is not a live mount and is not recorded as passing."
        ),
        details={
            "fusermount": fusermount,
            "fusermount3": fusermount3,
            "dev_fuse": dev_fuse,
            "live_mount_started": False,
            "presence_is_not_support": True,
        },
    )


def probe_live_mcp_server() -> QualificationProbe:
    return QualificationProbe(
        probe_id="live_mcp_server",
        present=False,
        evidence_kind="unavailable",
        live=False,
        simulated_represented_as_live=False,
        reason=(
            "No live MCP stdio, HTTP, or P2P server process was started. "
            "Support-matrix generation does not start MCP servers."
        ),
        details={
            "stdio_server_started": False,
            "http_server_started": False,
            "p2p_server_started": False,
        },
    )


def run_hermetic_matrix_suite(
    *,
    kit_root: Path | None = None,
    matrix: SupportMatrix | None = None,
) -> tuple[dict[str, Any], ...]:
    """Generate the matrix and check README. Not live qualification."""

    kit_root = Path(kit_root) if kit_root is not None else _kit_root()
    matrix = matrix or generate_authoritative_support_matrix()
    mappings = [row.to_mapping() for row in matrix.rows]
    used = {item["support_class"] for item in mappings}
    if used - set(SUPPORT_CLASSES):
        raise SupportMatrixQualificationError(
            "matrix used a class outside the closed vocabulary"
        )
    if set(SUPPORT_CLASSES) != set(matrix.closed_vocabulary):
        raise SupportMatrixQualificationError("closed vocabulary drifted")
    if any(item["live_support_claim"] for item in mappings):
        raise SupportMatrixQualificationError(
            "live_support_claim cannot be true without live evidence"
        )
    if any(item["support_class"] == "live_qualified" for item in mappings):
        raise SupportMatrixQualificationError(
            "live_qualified rows require live evidence in this evaluation"
        )
    if any(item["live"] for item in mappings):
        raise SupportMatrixQualificationError(
            "matrix generation cannot mark rows live without a live session"
        )
    if any(item["simulated"] and item["live"] for item in mappings):
        raise SupportMatrixQualificationError(
            "simulated results cannot be represented as live"
        )
    if any(item["hermetic"] and item["live"] for item in mappings):
        raise SupportMatrixQualificationError(
            "hermetic results cannot be represented as live"
        )
    unavailable_ids = {
        item["surface_id"]
        for item in mappings
        if item["support_class"] == "unavailable"
    }
    required_unavailable = {
        "pinned_ipfs",
        "linux_fuse_live",
        "container_fuse",
        "live_mcp_server",
    }
    if not required_unavailable <= unavailable_ids:
        raise SupportMatrixQualificationError(
            "missing environments must stay typed unavailable"
        )
    readme_path = kit_root / "README.md"
    if not readme_path.is_file():
        raise SupportMatrixQualificationError("Kit README.md is absent")
    readme = readme_path.read_text(encoding="utf-8")
    agreement = check_readme_against_matrix(readme, matrix)
    return (
        _passed(
            "closed_vocabulary_admitted",
            detail="Closed vocabulary admits all seven support classes",
            digests={"classes": ",".join(SUPPORT_CLASSES)},
        ),
        _passed(
            "every_row_uses_closed_class",
            detail="Every matrix row uses the closed support-class vocabulary",
            digests={"row_count": str(len(mappings)), "classes": ",".join(sorted(used))},
        ),
        _passed(
            "live_qualified_requires_live_evidence",
            detail="No live_qualified row was emitted without live evidence",
            digests={"live_qualified_row_count": "0"},
        ),
        _passed(
            "hermetic_not_represented_as_live",
            detail="Hermetic rows remain hermetic_qualified or non-live",
            digests={"hermetic_rows": str(sum(1 for item in mappings if item["hermetic"]))},
        ),
        _passed(
            "simulated_not_represented_as_live",
            detail="No simulated row is marked live",
            digests={"simulated_live_rows": "0"},
        ),
        _passed(
            "readme_claims_agree",
            detail="README support-matrix block matches the generated matrix",
            digests={
                "matrix_cid": str(agreement["matrix_cid"]),
                "row_count": str(agreement["row_count"]),
            },
        ),
        _passed(
            "missing_environments_typed_unavailable",
            detail="Missing IPFS, FUSE, container FUSE, and MCP server stay unavailable",
            digests={"unavailable_surfaces": ",".join(sorted(required_unavailable))},
        ),
        _passed(
            "zero_live_qualified_surfaces",
            detail="Current-head live_qualified count is zero",
            digests={"live_qualified_row_count": str(matrix.live_qualified_row_count)},
        ),
    )


def qualify_support_matrix(
    *,
    now: datetime | None = None,
    kit_root: Path | None = None,
) -> QualificationVerdict:
    """Qualify the support matrix and issue an R&D non-promotion."""

    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        raise SupportMatrixQualificationError("now must be timezone-aware")
    del reference

    ipfs_probe = probe_live_ipfs_transport()
    iroh_probe = probe_live_iroh_sidecar()
    fuse_probe = probe_live_linux_fuse_mount()
    mcp_probe = probe_live_mcp_server()
    generated = False
    matrix: SupportMatrix | None = None
    try:
        matrix = generate_authoritative_support_matrix()
        observations = run_hermetic_matrix_suite(kit_root=kit_root, matrix=matrix)
        generated = True
    except (SupportMatrixError, SupportMatrixQualificationError, OSError) as exc:
        reason = f"Support-matrix generation failed closed: {exc}."
        observations = tuple(
            _blocked(operation, reason=reason, limitations=("generation_failed",))
            for operation in REQUIRED_MATRIX_OPERATIONS
        )
        generated = False

    live_observations = (
        _blocked(
            "live_ipfs_transport",
            reason=ipfs_probe.reason,
            limitations=("ipfs_unavailable",),
        ),
        _blocked(
            "live_iroh_sidecar",
            reason=iroh_probe.reason,
            limitations=("sidecar_unavailable",),
        ),
        _blocked(
            "live_linux_fuse_mount",
            reason=fuse_probe.reason,
            limitations=("live_mount_not_exercised",),
        ),
        _blocked(
            "live_mcp_server",
            reason=mcp_probe.reason,
            limitations=("mcp_server_not_started",),
        ),
    )
    combined_observations = observations + live_observations
    passed_ops = tuple(
        item["operation"]
        for item in observations
        if item.get("status") == "passed"
    )
    missing = tuple(
        operation
        for operation in REQUIRED_MATRIX_OPERATIONS
        if operation not in passed_ops
    )
    hermetic_ops = tuple(
        _hermetic_operation(
            item["operation"],
            status=str(item["status"]),
            reason=str(item.get("detail") or item.get("reason") or ""),
            digests=item.get("digests") if isinstance(item.get("digests"), Mapping) else {},
        )
        for item in observations
    )
    live_unavailable_ops = (
        _live_unavailable_operation("live_ipfs_transport", reason=ipfs_probe.reason),
        _live_unavailable_operation("live_iroh_sidecar", reason=iroh_probe.reason),
        _live_unavailable_operation("live_linux_fuse_mount", reason=fuse_probe.reason),
        _live_unavailable_operation("live_mcp_server", reason=mcp_probe.reason),
    )
    contract = matrix_contract() if generated else {}
    matrix_cid = matrix.matrix_cid if matrix is not None else "unavailable"
    live_qualified_count = matrix.live_qualified_row_count if matrix is not None else 0
    readme_agrees = generated and "readme_claims_agree" in passed_ops
    probes = (
        QualificationProbe(
            probe_id="authoritative_support_matrix",
            present=generated,
            evidence_kind="measured_hermetic" if generated else "unavailable",
            live=False,
            simulated_represented_as_live=False,
            reason=(
                "AuthoritativeSupportMatrix@1 classified current-head Kit surfaces "
                "with the closed vocabulary. README claims match the generated "
                "matrix. Zero surfaces are live_qualified. This is not a closed "
                "PCPR release."
                if generated
                else "Support-matrix generation failed closed."
            ),
            details={
                "backend_id": BACKEND_ID,
                "schema": ADAPTER_SCHEMA,
                "interface": ADAPTER_INTERFACE,
                "policy": POLICY,
                "certification_scope": CERTIFICATION_SCOPE,
                "production_authorized": False,
                "live_support_claim": False,
                "support_class": SUPPORT_CLASS,
                "is_hermetic": True,
                "live_provider": False,
                "matrix_cid": matrix_cid,
                "row_count": len(matrix.rows) if matrix is not None else 0,
                "live_qualified_row_count": live_qualified_count,
                "closed_vocabulary": list(SUPPORT_CLASSES),
            },
        ),
        ipfs_probe,
        iroh_probe,
        fuse_probe,
        mcp_probe,
        QualificationProbe(
            probe_id="interface_parity_not_reopened",
            present=None,
            evidence_kind="unavailable",
            live=False,
            simulated_represented_as_live=False,
            reason=(
                "Python/CLI/MCP/MCP++ adapter parity is "
                f"{PCPR_026_TASK_ID}. This receipt does not reopen it."
            ),
            details={"remediating_task": PCPR_026_TASK_ID},
        ),
    )
    complete = generated and not missing
    disposition = (
        CertificationDisposition.CONDITIONAL.value
        if complete
        else CertificationDisposition.UNAVAILABLE.value
    )
    payload = {
        "schema": QUALIFICATION_VERDICT_SCHEMA,
        "interface": QUALIFICATION_INTERFACE,
        "promotion_status": "rnd_non_promoted",
        "supervisor_disposition": "supervisor_non_promoted",
        "closed_release_outcome": None,
        "release_claim": False,
        "completion_authoritative": False,
        "contracts_frozen": False,
        "duckdb_or_quack_state_written": False,
        "support_matrix_live_qualified": False,
        "suite_complete": False,
        "certification_disposition": disposition,
        "support_class": SUPPORT_CLASS,
        "live_support_claim": False,
        "simulated_results_represented_as_live": False,
        "hermetic_results_represented_as_live": False,
        "support_matrix_generated": complete,
        "readme_claims_agree": readme_agrees,
        "live_qualified_row_count": live_qualified_count,
        "live_ipfs_transport_qualified": False,
        "live_ipfs_evidence_kind": "unavailable",
        "this_task_created_competing_authority": False,
        "matrix_cid": matrix_cid,
        "probes": [item.to_mapping() for item in probes],
        "observations": list(combined_observations),
        "hermetic_operations": [dict(item) for item in hermetic_ops],
        "live_unavailable_operations": [dict(item) for item in live_unavailable_ops],
        "operations_observed": list(passed_ops),
        "operations_missing": list(missing) + list(LIVE_UNAVAILABLE_OPERATIONS),
        "blockers": [],
        "policy": contract.get("policy", POLICY),
    }
    _reject_closed_release_value(payload["promotion_status"], "promotion_status")
    _reject_closed_release_value(
        payload["supervisor_disposition"], "supervisor_disposition"
    )
    if payload["closed_release_outcome"] is not None:
        raise SupportMatrixQualificationError("closed_release_outcome must be null")
    if payload["promotion_status"] not in PROMOTION_STATUSES:
        raise SupportMatrixQualificationError("promotion_status is not admitted")
    if payload["promotion_status"] == "supervisor_promoted":
        raise SupportMatrixQualificationError(
            "PCPR-027 cannot promote the supervisor"
        )
    if payload["support_matrix_live_qualified"] is True:
        raise SupportMatrixQualificationError(
            "support_matrix_live_qualified cannot be true without live evidence"
        )
    if payload["live_support_claim"] is True:
        raise SupportMatrixQualificationError(
            "live_support_claim cannot be true for PCPR-027"
        )
    if payload["hermetic_results_represented_as_live"] is True:
        raise SupportMatrixQualificationError(
            "hermetic results cannot be represented as live"
        )
    if LIVE_SUPPORT_CLAIM is True:
        raise SupportMatrixQualificationError(
            "matrix surface live_support_claim must stay false"
        )
    cid_body = {key: payload[key] for key in payload if key != "verdict_cid"}
    cid = content_identity(cid_body)
    return QualificationVerdict(
        schema=payload["schema"],
        interface=payload["interface"],
        promotion_status=payload["promotion_status"],
        supervisor_disposition=payload["supervisor_disposition"],
        closed_release_outcome=None,
        release_claim=False,
        completion_authoritative=False,
        contracts_frozen=False,
        duckdb_or_quack_state_written=False,
        support_matrix_live_qualified=False,
        suite_complete=False,
        certification_disposition=payload["certification_disposition"],
        support_class=SUPPORT_CLASS,
        live_support_claim=False,
        simulated_results_represented_as_live=False,
        hermetic_results_represented_as_live=False,
        support_matrix_generated=bool(payload["support_matrix_generated"]),
        readme_claims_agree=bool(payload["readme_claims_agree"]),
        live_qualified_row_count=int(payload["live_qualified_row_count"]),
        live_ipfs_transport_qualified=False,
        live_ipfs_evidence_kind="unavailable",
        this_task_created_competing_authority=False,
        matrix_cid=str(payload["matrix_cid"]),
        probes=probes,
        observations=tuple(payload["observations"]),
        hermetic_operations=tuple(payload["hermetic_operations"]),
        live_unavailable_operations=tuple(payload["live_unavailable_operations"]),
        operations_observed=tuple(payload["operations_observed"]),
        operations_missing=tuple(payload["operations_missing"]),
        blockers=(),
        verdict_cid=cid,
    )


def qualify_current_head_support_matrix(
    *, now: datetime | None = None, kit_root: Path | None = None
) -> QualificationVerdict:
    return qualify_support_matrix(now=now, kit_root=kit_root)


def validate_pcpr_027_outer_receipt(payload: Mapping[str, Any]) -> None:
    """Reject closed-release claims and simulated-as-live promotion."""

    if not isinstance(payload, Mapping):
        raise SupportMatrixQualificationError("receipt must be a mapping")
    task_id = _text(payload.get("task_id"), "task_id")
    if task_id != PCPR_027_TASK_ID:
        raise SupportMatrixQualificationError("task_id must be PCPR-027")
    promotion = None
    acceptance = payload.get("acceptance")
    verdict = payload.get("qualification_verdict")
    if isinstance(acceptance, Mapping):
        promotion = acceptance.get("promotion_status")
        if acceptance.get("closed_release_outcome") is not None:
            raise SupportMatrixQualificationError(
                "acceptance.closed_release_outcome must be null"
            )
        if acceptance.get("release_claim") is True:
            raise SupportMatrixQualificationError(
                "acceptance.release_claim must be false"
            )
        if acceptance.get("support_matrix_live_qualified") is True:
            raise SupportMatrixQualificationError(
                "acceptance.support_matrix_live_qualified cannot be true without live evidence"
            )
    if isinstance(verdict, Mapping):
        promotion = verdict.get("promotion_status", promotion)
        if verdict.get("closed_release_outcome") is not None:
            raise SupportMatrixQualificationError(
                "qualification_verdict.closed_release_outcome must be null"
            )
        if verdict.get("support_matrix_live_qualified") is True:
            raise SupportMatrixQualificationError(
                "support_matrix_live_qualified cannot be true without live evidence"
            )
        if verdict.get("simulated_results_represented_as_live") is True:
            raise SupportMatrixQualificationError(
                "simulated results cannot be represented as live"
            )
        if verdict.get("hermetic_results_represented_as_live") is True:
            raise SupportMatrixQualificationError(
                "hermetic results cannot be represented as live"
            )
        if verdict.get("live_support_claim") is True:
            raise SupportMatrixQualificationError(
                "live_support_claim cannot be true without live evidence"
            )
        live_kind = verdict.get("live_ipfs_evidence_kind")
        if live_kind is not None:
            _kind(live_kind, "live_ipfs_evidence_kind")
        live_count = verdict.get("live_qualified_row_count")
        if live_count not in (None, 0):
            raise SupportMatrixQualificationError(
                "live_qualified_row_count must be zero without live evidence"
            )
    promotion_text = _text(promotion, "promotion_status")
    if promotion_text not in PROMOTION_STATUSES:
        raise SupportMatrixQualificationError("promotion_status is not admitted")
    if promotion_text in CLOSED_RELEASE_OUTCOMES:
        raise SupportMatrixQualificationError(
            "promotion_status is a closed release outcome"
        )
    legend = payload.get("evidence_legend")
    if legend is not None and not isinstance(legend, Mapping):
        raise SupportMatrixQualificationError(
            "evidence_legend must be a mapping when present"
        )


def observe_pcpr_027_sealed_environment() -> dict[str, Any]:
    """Sealed PATH observation plus typed-unavailable extra tools."""

    measured = dict(observe_sealed_validation_environment())
    measured["fusermount"] = sealed_which("fusermount")
    measured["fusermount3"] = sealed_which("fusermount3")
    measured["docker"] = sealed_which("docker")
    measured["podman"] = sealed_which("podman")
    measured["iroh"] = sealed_which("iroh")
    measured["ipfs-kit-iroh-sidecar"] = sealed_which("ipfs-kit-iroh-sidecar")
    measured["dev_fuse"] = "/dev/fuse" if Path("/dev/fuse").exists() else "unavailable"
    return measured


def generated_readme_block() -> str:
    """Helper for operators regenerating the README matrix section."""

    return render_readme_claims(generate_authoritative_support_matrix())


__all__ = [
    "QUALIFICATION_INTERFACE",
    "QUALIFICATION_SCHEMA",
    "QUALIFICATION_VERDICT_SCHEMA",
    "PCPR_027_TASK_ID",
    "PCPR_027_GOAL_ID",
    "HERMETIC_CANDIDATE_SUITES",
    "REQUIRED_MATRIX_OPERATIONS",
    "LIVE_UNAVAILABLE_OPERATIONS",
    "CLOSED_RELEASE_OUTCOMES",
    "SupportMatrixQualificationError",
    "QualificationVerdict",
    "refuse_simulated_as_live",
    "sealed_which",
    "probe_live_ipfs_transport",
    "probe_live_iroh_sidecar",
    "probe_live_linux_fuse_mount",
    "probe_live_mcp_server",
    "run_hermetic_matrix_suite",
    "qualify_support_matrix",
    "qualify_current_head_support_matrix",
    "validate_pcpr_027_outer_receipt",
    "observe_pcpr_027_sealed_environment",
    "generated_readme_block",
]

"""Fail-closed PCPR-025 sibling test-tree decoupling qualification.

PCPR-025 removes sitecustomize and harness sys.path injection of sibling
checkouts, replaces Datasets tests-tree fixture loading with packaged
vectors, and refuses monorepo sibling fallbacks. Live IPFS and
CLI/MCP/MCP++ parity stay typed unavailable. Hermetic source probes cannot
mint live qualification.

This module is not release authority: it does not write DuckDB or Quack
state and never emits a closed PCPR release outcome.
"""

from __future__ import annotations

import ast
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
from ipfs_kit_py.assurance.sibling_test_tree import (
    BACKEND_ID,
    CERTIFICATION_SCOPE,
    INTERFACE as ADAPTER_INTERFACE,
    LIVE_SUPPORT_CLAIM,
    SCHEMA as ADAPTER_SCHEMA,
    SUPPORT_CLASS,
    decoupling_contract,
)
from ipfs_kit_py.core.operation_contracts import content_identity


QUALIFICATION_INTERFACE: Final = "SiblingTestTreeQualification@1"
QUALIFICATION_SCHEMA: Final = (
    "ipfs_kit_py/assurance/sibling-test-tree-qualification@1"
)
QUALIFICATION_VERDICT_SCHEMA: Final = (
    "ipfs_kit_py/assurance/sibling-test-tree-qualification-verdict@1"
)

PCPR_025_TASK_ID: Final = "PCPR-025"
PCPR_025_GOAL_ID: Final = "PCPR-G300"
PCPR_024_TASK_ID: Final = "PCPR-024"
PCPR_026_TASK_ID: Final = "PCPR-026"
PCPR_027_TASK_ID: Final = "PCPR-027"
PCPR_PROGRAM_ID: Final = "proof-carrying-platform-qualification-and-release-v1"
PCPR_BOARD_NAMESPACE: Final = "proof-carrying-platform-qualification-and-release-v1"

HERMETIC_CANDIDATE_SUITES: Final[tuple[str, ...]] = (
    "tests/test_pcpr_sibling_test_tree_qualification.py",
)

REQUIRED_DECOUPLING_OPERATIONS: Final[tuple[str, ...]] = (
    "sitecustomize_no_sibling_sys_path",
    "runtime_readiness_harness_no_sys_path",
    "runtime_readiness_harness_no_test_tree_requirement",
    "kernel_vfs_harness_no_sys_path",
    "datasets_vectors_packaged",
    "coordination_vectors_no_monorepo_sibling",
)

LIVE_UNAVAILABLE_OPERATIONS: Final[tuple[str, ...]] = (
    "live_ipfs_transport",
    "interface_parity",
)


class SiblingTestTreeQualificationError(ValueError):
    """Malformed qualification evidence or a forbidden authority claim."""


@dataclass(frozen=True)
class QualificationVerdict:
    """Fail-closed PCPR-025 decoupling decision. Never a closed release."""

    schema: str
    interface: str
    promotion_status: str
    supervisor_disposition: str
    closed_release_outcome: None
    release_claim: bool
    completion_authoritative: bool
    contracts_frozen: bool
    duckdb_or_quack_state_written: bool
    sibling_test_tree_live_qualified: bool
    suite_complete: bool
    certification_disposition: str
    support_class: str
    live_support_claim: bool
    simulated_results_represented_as_live: bool
    hermetic_results_represented_as_live: bool
    hermetic_decoupling_observed: bool
    sibling_tests_package_required: bool
    sibling_checkout_required: bool
    interface_parity_qualified: bool
    live_ipfs_transport_qualified: bool
    live_ipfs_evidence_kind: str
    this_task_created_competing_authority: bool
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
            "sibling_test_tree_live_qualified": (
                self.sibling_test_tree_live_qualified
            ),
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
            "hermetic_decoupling_observed": self.hermetic_decoupling_observed,
            "sibling_tests_package_required": self.sibling_tests_package_required,
            "sibling_checkout_required": self.sibling_checkout_required,
            "interface_parity_qualified": self.interface_parity_qualified,
            "live_ipfs_transport_qualified": self.live_ipfs_transport_qualified,
            "live_ipfs_evidence_kind": self.live_ipfs_evidence_kind,
            "this_task_created_competing_authority": (
                self.this_task_created_competing_authority
            ),
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
        raise SiblingTestTreeQualificationError(f"{name} must be a non-empty string")
    return value.strip()


def _kind(value: Any, name: str) -> str:
    kind = _text(value, name)
    if kind not in EVIDENCE_KINDS:
        raise SiblingTestTreeQualificationError(
            f"{name} is not an admitted evidence kind"
        )
    return kind


def _reject_closed_release_value(value: Any, name: str) -> None:
    if isinstance(value, str) and value in CLOSED_RELEASE_OUTCOMES:
        raise SiblingTestTreeQualificationError(
            f"{name} must not be a closed PCPR release outcome"
        )


def _hermetic_passed(
    operation: str,
    *,
    digests: Mapping[str, str],
    limitations: tuple[str, ...] = (),
    detail: str | None = None,
) -> dict[str, Any]:
    return {
        "operation": operation,
        "status": "passed",
        "environment": "hermetic",
        "source": "hermetic_observed",
        "signature_valid": True,
        "freshness": "current",
        "digests": dict(digests),
        "limitations": list(limitations + ("hermetic_not_live",)),
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
    environment: str = "live",
) -> dict[str, Any]:
    return {
        "operation": operation,
        "status": "blocked",
        "environment": environment,
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
    digests: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "operation": operation,
        "status": status,
        "environment": "hermetic",
        "source": "hermetic_observed" if status == "passed" else "unavailable",
        "evidence_kind": "measured_hermetic" if status == "passed" else "unavailable",
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


def refuse_simulated_as_live(adapter: Any) -> None:
    """Hermetic, simulated, or live-claiming adapters cannot mint live evidence."""

    live_provider = bool(getattr(adapter, "live_provider", False))
    hermetic = bool(getattr(adapter, "is_hermetic", True))
    simulated = bool(getattr(adapter, "simulated", False))
    live_claim = bool(getattr(adapter, "live_support_claim", False))
    if hermetic or simulated or not live_provider or live_claim:
        raise SiblingTestTreeQualificationError(
            "hermetic or simulated adapters cannot mint live sibling-tree qualification"
        )
    if getattr(adapter, "backend_id", None) != BACKEND_ID:
        raise SiblingTestTreeQualificationError(
            "live sibling-tree qualification requires backend_id='sibling_test_tree'"
        )


def refuse_hermetic_as_live(adapter: Any) -> None:
    """Explicit alias: hermetic decoupling cannot be submitted as live."""

    refuse_simulated_as_live(adapter)


def sealed_which(name: str) -> str:
    """Resolve an executable on the sealed validation PATH only."""

    for directory in SEALED_PATH.split(":"):
        candidate = Path(directory) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return "unavailable"


def _kit_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _sys_path_insert_lines(source: str) -> tuple[int, ...]:
    tree = ast.parse(source)
    hits: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "insert":
            continue
        value = func.value
        if isinstance(value, ast.Attribute) and value.attr == "path":
            hits.append(int(getattr(node, "lineno", 0) or 0))
    return tuple(hits)


def _contains_needle(source: str, needle: str) -> bool:
    return needle in source


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
                "unavailable and is not recorded as zero or passing. Hermetic "
                "source probes are not live IPFS."
            )
        ),
        details={
            "ipfs": ipfs,
            "PATH": SEALED_PATH,
            "live_daemon_started": False,
            "injected_transport_is_not_live": True,
        },
    )


def probe_cli_mcp_surfaces() -> tuple[QualificationProbe, ...]:
    probes: list[QualificationProbe] = []
    surfaces = (
        ("cli", "ipfs_kit_py.cli", PCPR_026_TASK_ID),
        ("mcp", "ipfs_kit_py.mcp", PCPR_026_TASK_ID),
        ("mcpp", "ipfs_kit_py.mcp_server.mcplusplus", PCPR_026_TASK_ID),
    )
    for surface, module_name, remediating in surfaces:
        try:
            __import__(module_name)
            present = True
            reason = (
                f"{surface} source module {module_name} is importable. "
                f"No live {surface} session was exercised. "
                f"Parity remains typed unavailable until {remediating}."
            )
        except Exception as exc:  # noqa: BLE001 - honest import probe
            present = False
            reason = (
                f"{surface} module {module_name} was not imported "
                f"({type(exc).__name__}). Live {surface} parity is typed unavailable."
            )
        probes.append(
            QualificationProbe(
                probe_id=f"{surface}_sibling_tree_parity",
                present=present,
                evidence_kind="unavailable",
                live=False,
                simulated_represented_as_live=False,
                reason=reason,
                details={
                    "module": module_name,
                    "remediating_task": remediating,
                    "live_session": False,
                },
            )
        )
    return tuple(probes)


def run_hermetic_decoupling_suite() -> tuple[dict[str, Any], ...]:
    """Static current-tree probes that sibling test-tree coupling is removed."""

    root = _kit_root()
    observations: list[dict[str, Any]] = []

    sitecustomize = root / "sitecustomize.py"
    if not sitecustomize.is_file():
        raise SiblingTestTreeQualificationError("sitecustomize.py is missing")
    site_source = sitecustomize.read_text(encoding="utf-8")
    site_hits = _sys_path_insert_lines(site_source)
    if site_hits:
        raise SiblingTestTreeQualificationError(
            f"sitecustomize.py still inserts sys.path at lines {site_hits}"
        )
    observations.append(
        _hermetic_passed(
            "sitecustomize_no_sibling_sys_path",
            digests={"sys_path_insert_hits": "0", "bytes": str(len(site_source.encode("utf-8")))},
            detail="sitecustomize.py no longer prepends a sibling checkout onto sys.path",
        )
    )

    harness = root / "benchmarks" / "runtime_readiness" / "run.py"
    if not harness.is_file():
        raise SiblingTestTreeQualificationError("runtime-readiness harness is missing")
    harness_source = harness.read_text(encoding="utf-8")
    harness_hits = _sys_path_insert_lines(harness_source)
    if harness_hits:
        raise SiblingTestTreeQualificationError(
            f"runtime-readiness harness still inserts sys.path at lines {harness_hits}"
        )
    observations.append(
        _hermetic_passed(
            "runtime_readiness_harness_no_sys_path",
            digests={"sys_path_insert_hits": "0"},
            detail="runtime-readiness harness no longer injects the source tree onto sys.path",
        )
    )
    if _contains_needle(harness_source, "tests/runtime_readiness"):
        raise SiblingTestTreeQualificationError(
            "runtime-readiness harness still names a sibling tests/runtime_readiness tree"
        )
    observations.append(
        _hermetic_passed(
            "runtime_readiness_harness_no_test_tree_requirement",
            digests={"tests_runtime_readiness_needle": "absent"},
            detail="production identity no longer requires a sibling tests/ tree",
        )
    )

    kvfs = root / "benchmarks" / "kernel_vfs" / "run.py"
    if not kvfs.is_file():
        raise SiblingTestTreeQualificationError("kernel_vfs harness is missing")
    kvfs_source = kvfs.read_text(encoding="utf-8")
    kvfs_hits = _sys_path_insert_lines(kvfs_source)
    if kvfs_hits:
        raise SiblingTestTreeQualificationError(
            f"kernel_vfs harness still inserts sys.path at lines {kvfs_hits}"
        )
    observations.append(
        _hermetic_passed(
            "kernel_vfs_harness_no_sys_path",
            digests={"sys_path_insert_hits": "0"},
            detail="kernel_vfs harness no longer injects the source tree onto sys.path",
        )
    )

    fixtures = (
        root / "tests" / "adversarial_assurance_store" / "datasets_test_fixtures.py"
    )
    if not fixtures.is_file():
        raise SiblingTestTreeQualificationError("datasets_test_fixtures.py is missing")
    fixture_source = fixtures.read_text(encoding="utf-8")
    if "tests" in fixture_source and "unit" in fixture_source and "logic" in fixture_source:
        if "spec_from_file_location" in fixture_source:
            raise SiblingTestTreeQualificationError(
                "datasets_test_fixtures.py still loads a sibling Datasets tests/ tree"
            )
    if "normative_vectors" not in fixture_source:
        raise SiblingTestTreeQualificationError(
            "datasets_test_fixtures.py does not import packaged normative vectors"
        )
    catalog = decoupling_contract()["vector_catalog"]
    if not isinstance(catalog, Mapping) or catalog.get("sibling_tests_package_required") is not False:
        raise SiblingTestTreeQualificationError(
            "packaged vectors still require a sibling tests package"
        )
    observations.append(
        _hermetic_passed(
            "datasets_vectors_packaged",
            digests={
                "schema": str(catalog.get("schema")),
                "sibling_tests_package_required": "false",
            },
            detail="Datasets assurance constructors load from packaged Kit vectors",
        )
    )

    coordination = root / "tests" / "test_coordination_storage.py"
    if not coordination.is_file():
        raise SiblingTestTreeQualificationError("test_coordination_storage.py is missing")
    coordination_source = coordination.read_text(encoding="utf-8")
    if ' / "Mcp-Plus-Plus"' in coordination_source or " / 'Mcp-Plus-Plus'" in coordination_source:
        raise SiblingTestTreeQualificationError(
            "test_coordination_storage.py still falls back to a monorepo sibling checkout"
        )
    observations.append(
        _hermetic_passed(
            "coordination_vectors_no_monorepo_sibling",
            digests={"monorepo_sibling_fallback": "absent"},
            detail="Profile G vectors use the vendored kit fixture, not a sibling checkout",
        )
    )

    observed = {item["operation"] for item in observations}
    if observed != set(REQUIRED_DECOUPLING_OPERATIONS):
        raise SiblingTestTreeQualificationError(
            f"hermetic decoupling operations mismatch: {sorted(observed)}"
        )
    return tuple(observations)


def qualify_sibling_test_tree(
    *,
    now: datetime | None = None,
) -> QualificationVerdict:
    """Qualify sibling-tree decoupling and issue an R&D non-promotion."""

    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        raise SiblingTestTreeQualificationError("now must be timezone-aware")
    del reference

    ipfs_probe = probe_live_ipfs_transport()
    hermetic_observed = False
    try:
        observations = run_hermetic_decoupling_suite()
        hermetic_observed = True
    except (SiblingTestTreeQualificationError, OSError, SyntaxError) as exc:
        reason = f"Hermetic sibling-tree decoupling suite failed closed: {exc}."
        observations = tuple(
            _blocked(operation, reason=reason, environment="hermetic")
            for operation in REQUIRED_DECOUPLING_OPERATIONS
        )
        hermetic_observed = False

    live_observations = (
        _blocked(
            "live_ipfs_transport",
            reason=ipfs_probe.reason,
            limitations=(
                "ipfs_unavailable" if not ipfs_probe.present else "daemon_not_started",
            ),
        ),
        _blocked(
            "interface_parity",
            reason=(
                "Hermetic sibling-tree decoupling was observed. "
                "CLI, MCP, and MCP++ sessions were not exercised. "
                f"{PCPR_026_TASK_ID} owns interface parity."
            ),
            limitations=(
                "hermetic_observed" if hermetic_observed else "hermetic_failed",
                "cli_unavailable",
                "mcp_unavailable",
                "mcpp_unavailable",
            ),
        ),
    )
    combined_observations = observations + live_observations
    python_ops = tuple(
        item["operation"]
        for item in observations
        if item.get("status") == "passed"
    )
    missing = tuple(
        operation
        for operation in REQUIRED_DECOUPLING_OPERATIONS
        if operation not in python_ops
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
        _live_unavailable_operation(
            "interface_parity",
            reason=(
                "CLI, MCP, and MCP++ sessions were not exercised. "
                f"{PCPR_026_TASK_ID} owns interface parity."
            ),
        ),
    )
    contract = decoupling_contract()
    probes = (
        QualificationProbe(
            probe_id="hermetic_sibling_test_tree_surface",
            present=hermetic_observed,
            evidence_kind="measured_hermetic" if hermetic_observed else "unavailable",
            live=False,
            simulated_represented_as_live=False,
            reason=(
                "Sitecustomize and harnesses no longer inject sibling checkouts; "
                "Datasets constructors are packaged Kit vectors; Profile G has no "
                "monorepo sibling fallback."
                if hermetic_observed
                else "Hermetic sibling-tree decoupling suite failed closed."
            ),
            details={
                "backend_id": BACKEND_ID,
                "schema": ADAPTER_SCHEMA,
                "interface": ADAPTER_INTERFACE,
                "certification_scope": CERTIFICATION_SCOPE,
                "production_authorized": False,
                "live_support_claim": False,
                "support_class": SUPPORT_CLASS,
                "is_hermetic": True,
                "live_provider": False,
                "sibling_tests_package_required": contract["sibling_tests_package_required"],
                "sibling_checkout_required": contract["sibling_checkout_required"],
            },
        ),
        ipfs_probe,
        *probe_cli_mcp_surfaces(),
        QualificationProbe(
            probe_id="proof_seal_not_reopened",
            present=None,
            evidence_kind="unavailable",
            live=False,
            simulated_represented_as_live=False,
            reason=(
                "Proof-seal store qualification is "
                f"{PCPR_024_TASK_ID}. This receipt does not reopen it."
            ),
            details={"remediating_task": PCPR_024_TASK_ID},
        ),
        QualificationProbe(
            probe_id="support_matrix_not_generated",
            present=False,
            evidence_kind="unavailable",
            live=False,
            simulated_represented_as_live=False,
            reason=(
                "Authoritative support-matrix generation is "
                f"{PCPR_027_TASK_ID}. This receipt does not replace it."
            ),
            details={"remediating_task": PCPR_027_TASK_ID},
        ),
    )
    disposition = (
        CertificationDisposition.CONDITIONAL.value
        if hermetic_observed and not missing
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
        "sibling_test_tree_live_qualified": False,
        "suite_complete": False,
        "certification_disposition": disposition,
        "support_class": SUPPORT_CLASS,
        "live_support_claim": False,
        "simulated_results_represented_as_live": False,
        "hermetic_results_represented_as_live": False,
        "hermetic_decoupling_observed": hermetic_observed
        and set(python_ops) >= set(REQUIRED_DECOUPLING_OPERATIONS),
        "sibling_tests_package_required": False,
        "sibling_checkout_required": False,
        "interface_parity_qualified": False,
        "live_ipfs_transport_qualified": False,
        "live_ipfs_evidence_kind": "unavailable",
        "this_task_created_competing_authority": False,
        "probes": [item.to_mapping() for item in probes],
        "observations": list(combined_observations),
        "hermetic_operations": [dict(item) for item in hermetic_ops],
        "live_unavailable_operations": [dict(item) for item in live_unavailable_ops],
        "operations_observed": list(python_ops),
        "operations_missing": list(missing) + list(LIVE_UNAVAILABLE_OPERATIONS),
        "blockers": [],
    }
    _reject_closed_release_value(payload["promotion_status"], "promotion_status")
    _reject_closed_release_value(
        payload["supervisor_disposition"], "supervisor_disposition"
    )
    if payload["closed_release_outcome"] is not None:
        raise SiblingTestTreeQualificationError("closed_release_outcome must be null")
    if payload["promotion_status"] not in PROMOTION_STATUSES:
        raise SiblingTestTreeQualificationError("promotion_status is not admitted")
    if payload["promotion_status"] == "supervisor_promoted":
        raise SiblingTestTreeQualificationError(
            "PCPR-025 cannot promote the supervisor"
        )
    if payload["sibling_test_tree_live_qualified"] is True:
        raise SiblingTestTreeQualificationError(
            "sibling_test_tree_live_qualified cannot be true without live evidence"
        )
    if payload["live_support_claim"] is True:
        raise SiblingTestTreeQualificationError(
            "live_support_claim cannot be true for PCPR-025"
        )
    if payload["hermetic_results_represented_as_live"] is True:
        raise SiblingTestTreeQualificationError(
            "hermetic results cannot be represented as live"
        )
    cid = content_identity({key: payload[key] for key in payload if key != "verdict_cid"})
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
        sibling_test_tree_live_qualified=False,
        suite_complete=False,
        certification_disposition=payload["certification_disposition"],
        support_class=SUPPORT_CLASS,
        live_support_claim=False,
        simulated_results_represented_as_live=False,
        hermetic_results_represented_as_live=False,
        hermetic_decoupling_observed=bool(payload["hermetic_decoupling_observed"]),
        sibling_tests_package_required=False,
        sibling_checkout_required=False,
        interface_parity_qualified=False,
        live_ipfs_transport_qualified=False,
        live_ipfs_evidence_kind="unavailable",
        this_task_created_competing_authority=False,
        probes=probes,
        observations=tuple(payload["observations"]),
        hermetic_operations=tuple(payload["hermetic_operations"]),
        live_unavailable_operations=tuple(payload["live_unavailable_operations"]),
        operations_observed=tuple(payload["operations_observed"]),
        operations_missing=tuple(payload["operations_missing"]),
        blockers=(),
        verdict_cid=cid,
    )


def qualify_current_head_sibling_test_tree(
    *, now: datetime | None = None
) -> QualificationVerdict:
    return qualify_sibling_test_tree(now=now)


def validate_pcpr_025_outer_receipt(payload: Mapping[str, Any]) -> None:
    """Reject closed-release claims and simulated-as-live promotion."""

    if not isinstance(payload, Mapping):
        raise SiblingTestTreeQualificationError("receipt must be a mapping")
    task_id = _text(payload.get("task_id"), "task_id")
    if task_id != PCPR_025_TASK_ID:
        raise SiblingTestTreeQualificationError("task_id must be PCPR-025")
    promotion = None
    acceptance = payload.get("acceptance")
    verdict = payload.get("qualification_verdict")
    if isinstance(acceptance, Mapping):
        promotion = acceptance.get("promotion_status")
        if acceptance.get("closed_release_outcome") is not None:
            raise SiblingTestTreeQualificationError(
                "acceptance.closed_release_outcome must be null"
            )
        if acceptance.get("release_claim") is True:
            raise SiblingTestTreeQualificationError(
                "acceptance.release_claim must be false"
            )
        if acceptance.get("sibling_test_tree_live_qualified") is True:
            raise SiblingTestTreeQualificationError(
                "acceptance.sibling_test_tree_live_qualified cannot be true without live evidence"
            )
    if isinstance(verdict, Mapping):
        promotion = verdict.get("promotion_status", promotion)
        if verdict.get("closed_release_outcome") is not None:
            raise SiblingTestTreeQualificationError(
                "qualification_verdict.closed_release_outcome must be null"
            )
        if verdict.get("sibling_test_tree_live_qualified") is True:
            raise SiblingTestTreeQualificationError(
                "sibling_test_tree_live_qualified cannot be true without live evidence"
            )
        if verdict.get("simulated_results_represented_as_live") is True:
            raise SiblingTestTreeQualificationError(
                "simulated results cannot be represented as live"
            )
        if verdict.get("hermetic_results_represented_as_live") is True:
            raise SiblingTestTreeQualificationError(
                "hermetic results cannot be represented as live"
            )
        if verdict.get("live_support_claim") is True:
            raise SiblingTestTreeQualificationError(
                "live_support_claim cannot be true without live evidence"
            )
        live_kind = verdict.get("live_ipfs_evidence_kind")
        if live_kind is not None:
            _kind(live_kind, "live_ipfs_evidence_kind")
    promotion_text = _text(promotion, "promotion_status")
    if promotion_text not in PROMOTION_STATUSES:
        raise SiblingTestTreeQualificationError("promotion_status is not admitted")
    if promotion_text in CLOSED_RELEASE_OUTCOMES:
        raise SiblingTestTreeQualificationError(
            "promotion_status is a closed release outcome"
        )
    legend = payload.get("evidence_legend")
    if legend is not None and not isinstance(legend, Mapping):
        raise SiblingTestTreeQualificationError(
            "evidence_legend must be a mapping when present"
        )


def observe_pcpr_025_sealed_environment() -> dict[str, Any]:
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


__all__ = [
    "QUALIFICATION_INTERFACE",
    "QUALIFICATION_SCHEMA",
    "QUALIFICATION_VERDICT_SCHEMA",
    "PCPR_025_TASK_ID",
    "PCPR_025_GOAL_ID",
    "CLOSED_RELEASE_OUTCOMES",
    "PROMOTION_STATUSES",
    "HERMETIC_CANDIDATE_SUITES",
    "REQUIRED_DECOUPLING_OPERATIONS",
    "LIVE_UNAVAILABLE_OPERATIONS",
    "SiblingTestTreeQualificationError",
    "QualificationVerdict",
    "refuse_simulated_as_live",
    "refuse_hermetic_as_live",
    "sealed_which",
    "probe_live_ipfs_transport",
    "run_hermetic_decoupling_suite",
    "qualify_sibling_test_tree",
    "qualify_current_head_sibling_test_tree",
    "validate_pcpr_025_outer_receipt",
    "observe_pcpr_025_sealed_environment",
    "observe_sealed_validation_environment",
]

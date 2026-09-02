"""Fail-closed PCPR-026 Python/CLI/MCP/MCP++ parity qualification.

PCPR-026 exercises local-durable put/get/digest/delete through the canonical
Python, CLI, MCP, and MCP++ adapters under AllInterfaceParityPolicy@1. Live
MCP server processes and pinned IPFS stay typed unavailable. Adapter sessions
cannot mint a closed PCPR release.

This module is not release authority: it does not write DuckDB or Quack
state and never emits a closed PCPR release outcome.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

from ipfs_kit_py.assurance.backend_certification import CertificationDisposition
from ipfs_kit_py.assurance.interface_parity import (
    BACKEND_ID,
    CERTIFICATION_SCOPE,
    INTERFACE as ADAPTER_INTERFACE,
    LIVE_SUPPORT_CLAIM,
    OPERATIONS,
    POLICY,
    SCHEMA as ADAPTER_SCHEMA,
    SUPPORT_CLASS,
    SURFACES,
    InterfaceParityError,
    InterfaceParityStack,
    build_parity_stack,
    call_mcp,
    call_mcp_jsonrpc,
    call_mcpp_framed,
    call_python,
    invoke_cli,
    make_request,
    parity_cid,
    parity_contract,
    refuse_simulated_as_live,
    resulting_cid,
    run_cli_stdout,
    semantic_payload,
    strip_transport_fields,
)
from ipfs_kit_py.assurance.local_backend_qualification import (
    CLOSED_RELEASE_OUTCOMES,
    EVIDENCE_KINDS,
    PROMOTION_STATUSES,
    SEALED_PATH,
    QualificationProbe,
    observe_sealed_validation_environment,
)
from ipfs_kit_py.core.operation_contracts import content_identity


QUALIFICATION_INTERFACE: Final = "InterfaceParityQualification@1"
QUALIFICATION_SCHEMA: Final = (
    "ipfs_kit_py/assurance/interface-parity-qualification@1"
)
QUALIFICATION_VERDICT_SCHEMA: Final = (
    "ipfs_kit_py/assurance/interface-parity-qualification-verdict@1"
)

PCPR_026_TASK_ID: Final = "PCPR-026"
PCPR_026_GOAL_ID: Final = "PCPR-G300"
PCPR_025_TASK_ID: Final = "PCPR-025"
PCPR_027_TASK_ID: Final = "PCPR-027"
PCPR_PROGRAM_ID: Final = "proof-carrying-platform-qualification-and-release-v1"
PCPR_BOARD_NAMESPACE: Final = "proof-carrying-platform-qualification-and-release-v1"

HERMETIC_CANDIDATE_SUITES: Final[tuple[str, ...]] = (
    "tests/test_pcpr_interface_parity_qualification.py",
)

REQUIRED_PARITY_OPERATIONS: Final[tuple[str, ...]] = (
    "python_write_read_digest_delete",
    "cli_write_read_digest_delete",
    "mcp_write_read_digest_delete",
    "mcpp_write_read_digest_delete",
    "semantic_payload_parity",
    "cid_identity_parity",
    "error_parity",
)

LIVE_UNAVAILABLE_OPERATIONS: Final[tuple[str, ...]] = (
    "live_mcp_server",
    "live_ipfs_transport",
)


class InterfaceParityQualificationError(ValueError):
    """Malformed qualification evidence or a forbidden authority claim."""


@dataclass(frozen=True)
class QualificationVerdict:
    """Fail-closed PCPR-026 parity decision. Never a closed release."""

    schema: str
    interface: str
    promotion_status: str
    supervisor_disposition: str
    closed_release_outcome: None
    release_claim: bool
    completion_authoritative: bool
    contracts_frozen: bool
    duckdb_or_quack_state_written: bool
    interface_parity_live_qualified: bool
    suite_complete: bool
    certification_disposition: str
    support_class: str
    live_support_claim: bool
    simulated_results_represented_as_live: bool
    hermetic_results_represented_as_live: bool
    adapter_parity_observed: bool
    interface_parity_qualified: bool
    live_server_parity_qualified: bool
    live_ipfs_transport_qualified: bool
    live_ipfs_evidence_kind: str
    this_task_created_competing_authority: bool
    probes: tuple[QualificationProbe, ...]
    observations: tuple[dict[str, Any], ...]
    adapter_operations: tuple[dict[str, Any], ...]
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
            "interface_parity_live_qualified": self.interface_parity_live_qualified,
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
            "adapter_parity_observed": self.adapter_parity_observed,
            "interface_parity_qualified": self.interface_parity_qualified,
            "live_server_parity_qualified": self.live_server_parity_qualified,
            "live_ipfs_transport_qualified": self.live_ipfs_transport_qualified,
            "live_ipfs_evidence_kind": self.live_ipfs_evidence_kind,
            "this_task_created_competing_authority": (
                self.this_task_created_competing_authority
            ),
            "probes": [item.to_mapping() for item in self.probes],
            "observations": [dict(item) for item in self.observations],
            "adapter_operations": [dict(item) for item in self.adapter_operations],
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
        raise InterfaceParityQualificationError(f"{name} must be a non-empty string")
    return value.strip()


def _kind(value: Any, name: str) -> str:
    kind = _text(value, name)
    if kind not in EVIDENCE_KINDS:
        raise InterfaceParityQualificationError(
            f"{name} is not an admitted evidence kind"
        )
    return kind


def _reject_closed_release_value(value: Any, name: str) -> None:
    if isinstance(value, str) and value in CLOSED_RELEASE_OUTCOMES:
        raise InterfaceParityQualificationError(
            f"{name} must not be a closed PCPR release outcome"
        )


def _passed(
    operation: str,
    *,
    digests: Mapping[str, str],
    limitations: tuple[str, ...] = (),
    detail: str | None = None,
    environment: str = "live",
    source: str = "live_observed",
    evidence_kind: str = "measured",
    live: bool = False,
) -> dict[str, Any]:
    return {
        "operation": operation,
        "status": "passed",
        "environment": environment,
        "source": source,
        "signature_valid": True,
        "freshness": "current",
        "digests": dict(digests),
        "limitations": list(limitations),
        "detail": detail,
        "evidence_kind": evidence_kind,
        "live": live,
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


def _adapter_operation(
    operation: str,
    *,
    status: str,
    reason: str,
    digests: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    passed = status == "passed"
    return {
        "operation": operation,
        "status": status,
        "environment": "adapter",
        "source": "adapter_observed" if passed else "unavailable",
        "evidence_kind": "measured" if passed else "unavailable",
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
                "unavailable and is not recorded as zero or passing. Adapter "
                "sessions against the local POSIX store are not live IPFS."
            )
        ),
        details={
            "ipfs": ipfs,
            "PATH": SEALED_PATH,
            "live_daemon_started": False,
            "injected_transport_is_not_live": True,
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
            "In-process MCPToolAdapter and MCPPlusPlusToolAdapter JSON-RPC "
            "and framing fixtures are not live server sessions."
        ),
        details={
            "stdio_server_started": False,
            "http_server_started": False,
            "p2p_server_started": False,
            "injected_adapter_is_not_live_server": True,
        },
    )


def probe_surface_modules() -> tuple[QualificationProbe, ...]:
    surfaces = (
        ("cli", "ipfs_kit_py.cli.operation_adapter"),
        ("mcp", "ipfs_kit_py.mcp_server.tools.operation_adapter"),
        ("mcpp", "ipfs_kit_py.mcp_server.tools.operation_adapter"),
        ("python", "ipfs_kit_py.high_level_api.operation_adapter"),
    )
    probes: list[QualificationProbe] = []
    for surface, module_name in surfaces:
        try:
            __import__(module_name)
            present = True
            reason = (
                f"{surface} adapter module {module_name} is importable and was "
                "exercised as an in-process adapter session against the live "
                "local POSIX store. That is not a live network server."
            )
        except Exception as exc:  # noqa: BLE001 - honest import probe
            present = False
            reason = (
                f"{surface} module {module_name} was not imported "
                f"({type(exc).__name__}). Live {surface} parity is typed "
                "unavailable."
            )
        probes.append(
            QualificationProbe(
                probe_id=f"{surface}_adapter_session",
                present=present,
                evidence_kind="measured" if present else "unavailable",
                live=False,
                simulated_represented_as_live=False,
                reason=reason,
                details={
                    "module": module_name,
                    "live_session": False,
                    "adapter_session": present,
                },
            )
        )
    return tuple(probes)


def _require_success(response: Any, *, surface: str, operation: str) -> str:
    payload = response.to_dict() if hasattr(response, "to_dict") else dict(response)
    if payload.get("success") is not True:
        raise InterfaceParityQualificationError(
            f"{surface} {operation} did not succeed: {payload.get('error')}"
        )
    return resulting_cid(response)


def _require_failure(response: Any, *, surface: str, operation: str) -> str:
    payload = response.to_dict() if hasattr(response, "to_dict") else dict(response)
    if payload.get("success") is True:
        raise InterfaceParityQualificationError(
            f"{surface} {operation} unexpectedly succeeded"
        )
    error = payload.get("error") or {}
    code = error.get("code") if isinstance(error, Mapping) else None
    if code not in {"E_NOT_FOUND", "not_found", "NOT_FOUND"} and str(code) not in {
        "not_found",
        "E_NOT_FOUND",
    }:
        # StorageError.to_record uses the enum value.
        if not (isinstance(error, Mapping) and "NOT_FOUND" in str(error.get("code", ""))):
            if not (isinstance(error, Mapping) and str(error.get("code", "")).endswith("NOT_FOUND")):
                if not (
                    isinstance(error, Mapping)
                    and str(error.get("code", "")).lower() in {"not_found", "e_not_found"}
                ):
                    raw = str(error.get("code", "")) if isinstance(error, Mapping) else ""
                    if "not_found" not in raw.lower():
                        raise InterfaceParityQualificationError(
                            f"{surface} {operation} error is not NOT_FOUND: {error}"
                        )
    return str(code or "NOT_FOUND")


def _surface_cycle(
    stack: InterfaceParityStack,
    surface: str,
    *,
    put,
    get,
    digest,
    delete,
) -> tuple[str, Any, Any]:
    path = f"objects/{surface}.bin"
    put_req = make_request("put", path, request_id=f"pcpr-026-{surface}-put")
    get_req = make_request("get", path, request_id=f"pcpr-026-{surface}-get")
    digest_req = make_request("digest", path, request_id=f"pcpr-026-{surface}-digest")
    delete_req = make_request("delete", path, request_id=f"pcpr-026-{surface}-delete")
    put_response = put(put_req)
    cid = _require_success(put_response, surface=surface, operation="put")
    expected = parity_cid()
    if cid != expected:
        raise InterfaceParityQualificationError(
            f"{surface} put CID {cid} != expected {expected}"
        )
    get_response = get(get_req)
    if _require_success(get_response, surface=surface, operation="get") != cid:
        raise InterfaceParityQualificationError(f"{surface} get CID drifted")
    digest_response = digest(digest_req)
    if _require_success(digest_response, surface=surface, operation="digest") != cid:
        raise InterfaceParityQualificationError(f"{surface} digest CID drifted")
    delete_response = delete(delete_req)
    _require_success(delete_response, surface=surface, operation="delete")
    missing = get(make_request("get", path, request_id=f"pcpr-026-{surface}-missing"))
    _require_failure(missing, surface=surface, operation="get-missing")
    return cid, get_response, missing


def run_adapter_parity_suite(root: Path) -> tuple[dict[str, Any], ...]:
    """Exercise python/cli/mcp/mcpp adapters against the live local store."""

    stack = build_parity_stack(root)
    refuse_simulated_as_live(stack.store)
    observations: list[dict[str, Any]] = []
    try:
        expected_cid = parity_cid()
        python_cid, python_get, python_missing = _surface_cycle(
            stack,
            "python",
            put=lambda req: call_python(stack, "put", req),
            get=lambda req: call_python(stack, "get", req),
            digest=lambda req: call_python(stack, "digest", req),
            delete=lambda req: call_python(stack, "delete", req),
        )
        observations.append(
            _passed(
                "python_write_read_digest_delete",
                digests={"cid": python_cid, "surface": "python"},
                limitations=("adapter_not_live_server",),
                detail="PythonAdapter put/get/digest/delete against live POSIX",
                live=True,
                evidence_kind="measured_live",
                source="live_observed",
                environment="live",
            )
        )

        cli_cid, cli_get, cli_missing = _surface_cycle(
            stack,
            "cli",
            put=lambda req: invoke_cli(stack, "put", req),
            get=lambda req: invoke_cli(stack, "get", req),
            digest=lambda req: invoke_cli(stack, "digest", req),
            delete=lambda req: invoke_cli(stack, "delete", req),
        )
        cli_code, cli_stdout = run_cli_stdout(
            stack,
            "put",
            make_request("put", "objects/cli-stdout.bin", request_id="pcpr-026-cli-stdout-put"),
        )
        if cli_code != 0:
            raise InterfaceParityQualificationError("CLI stdout put exited non-zero")
        if resulting_cid(cli_stdout) != expected_cid:
            raise InterfaceParityQualificationError("CLI stdout CID drifted")
        observations.append(
            _passed(
                "cli_write_read_digest_delete",
                digests={"cid": cli_cid, "stdout_exit_code": str(cli_code)},
                limitations=("adapter_not_live_server", "in_process_cli"),
                detail="CLIAdapter invoke and run against live POSIX",
                evidence_kind="measured",
                source="adapter_observed",
                environment="adapter",
            )
        )

        mcp_cid, mcp_get, mcp_missing = _surface_cycle(
            stack,
            "mcp",
            put=lambda req: call_mcp(stack, "put", req),
            get=lambda req: call_mcp(stack, "get", req),
            digest=lambda req: call_mcp(stack, "digest", req),
            delete=lambda req: call_mcp(stack, "delete", req),
        )
        rpc = call_mcp_jsonrpc(
            stack,
            "put",
            make_request("put", "objects/mcp-jsonrpc.bin", request_id="pcpr-026-mcp-jsonrpc-put"),
        )
        rpc_result = rpc.get("result") if isinstance(rpc, Mapping) else None
        if not isinstance(rpc_result, Mapping) or rpc_result.get("success") is not True:
            raise InterfaceParityQualificationError("MCP JSON-RPC put did not succeed")
        if resulting_cid(rpc_result) != expected_cid:
            raise InterfaceParityQualificationError("MCP JSON-RPC CID drifted")
        observations.append(
            _passed(
                "mcp_write_read_digest_delete",
                digests={"cid": mcp_cid, "jsonrpc": "tools/call"},
                limitations=("adapter_not_live_server", "in_process_jsonrpc"),
                detail="MCPToolAdapter call and JSON-RPC tools/call against live POSIX",
                evidence_kind="measured",
                source="adapter_observed",
                environment="adapter",
            )
        )

        mcpp_cid, mcpp_get, mcpp_missing = _surface_cycle(
            stack,
            "mcpp",
            put=lambda req: call_mcpp_framed(stack, "put", req, framing="stdio"),
            get=lambda req: call_mcpp_framed(stack, "get", req, framing="stdio"),
            digest=lambda req: call_mcpp_framed(stack, "digest", req, framing="stdio"),
            delete=lambda req: call_mcpp_framed(stack, "delete", req, framing="stdio"),
        )
        for framing in ("http", "p2p"):
            framed = call_mcpp_framed(
                stack,
                "get",
                make_request("get", "objects/mcp-jsonrpc.bin", request_id=f"pcpr-026-mcpp-{framing}-get"),
                framing=framing,
            )
            if resulting_cid(framed) != expected_cid:
                raise InterfaceParityQualificationError(
                    f"MCP++ {framing} get CID drifted"
                )
        observations.append(
            _passed(
                "mcpp_write_read_digest_delete",
                digests={"cid": mcpp_cid, "framings": "stdio,http,p2p"},
                limitations=("adapter_not_live_server", "in_process_framing"),
                detail="MCPPlusPlusToolAdapter stdio/http/p2p fixtures against live POSIX",
                evidence_kind="measured",
                source="adapter_observed",
                environment="adapter",
            )
        )

        cids = {python_cid, cli_cid, mcp_cid, mcpp_cid, expected_cid}
        if cids != {expected_cid}:
            raise InterfaceParityQualificationError(
                f"cross-transport CID set drifted: {sorted(cids)}"
            )
        observations.append(
            _passed(
                "cid_identity_parity",
                digests={"cid": expected_cid, "surfaces": ",".join(SURFACES)},
                limitations=("adapter_not_live_server",),
                detail="put of the same bytes produced one CID on every surface",
                evidence_kind="measured",
                source="adapter_observed",
                environment="adapter",
            )
        )

        python_semantic = semantic_payload(python_get)
        if semantic_payload(cli_get) != python_semantic:
            raise InterfaceParityQualificationError("CLI get semantic payload drifted")
        if semantic_payload(mcp_get) != python_semantic:
            raise InterfaceParityQualificationError("MCP get semantic payload drifted")
        if strip_transport_fields(mcpp_get) != python_semantic:
            raise InterfaceParityQualificationError("MCP++ get semantic payload drifted")
        observations.append(
            _passed(
                "semantic_payload_parity",
                digests={
                    "policy": POLICY,
                    "cid": expected_cid,
                    "surfaces": ",".join(SURFACES),
                },
                limitations=("adapter_not_live_server", "transport_fields_stripped"),
                detail="get payloads match across python/cli/mcp/mcpp after strip",
                evidence_kind="measured",
                source="adapter_observed",
                environment="adapter",
            )
        )

        python_err = semantic_payload(python_missing)
        if semantic_payload(cli_missing) != python_err:
            raise InterfaceParityQualificationError("CLI missing-get error drifted")
        if semantic_payload(mcp_missing) != python_err:
            raise InterfaceParityQualificationError("MCP missing-get error drifted")
        if strip_transport_fields(mcpp_missing) != python_err:
            raise InterfaceParityQualificationError("MCP++ missing-get error drifted")
        observations.append(
            _passed(
                "error_parity",
                digests={"error": "NOT_FOUND", "surfaces": ",".join(SURFACES)},
                limitations=("adapter_not_live_server",),
                detail="missing-path get is NOT_FOUND on every surface",
                evidence_kind="measured",
                source="adapter_observed",
                environment="adapter",
            )
        )
    finally:
        stack.close()

    observed = {item["operation"] for item in observations}
    if observed != set(REQUIRED_PARITY_OPERATIONS):
        raise InterfaceParityQualificationError(
            f"parity operations mismatch: {sorted(observed)}"
        )
    return tuple(observations)


def qualify_interface_parity(
    *,
    root: Path | None = None,
    now: datetime | None = None,
) -> QualificationVerdict:
    """Qualify adapter parity and issue an R&D non-promotion."""

    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        raise InterfaceParityQualificationError("now must be timezone-aware")
    del reference

    ipfs_probe = probe_live_ipfs_transport()
    mcp_server_probe = probe_live_mcp_server()
    owned_root = root is None
    work_root = Path(root) if root is not None else Path(
        tempfile.mkdtemp(prefix="pcpr-026-parity-")
    )
    adapter_observed = False
    try:
        observations = run_adapter_parity_suite(work_root)
        adapter_observed = True
    except (InterfaceParityError, InterfaceParityQualificationError, OSError) as exc:
        reason = f"Adapter parity suite failed closed: {exc}."
        observations = tuple(
            _blocked(operation, reason=reason, environment="adapter")
            for operation in REQUIRED_PARITY_OPERATIONS
        )
        adapter_observed = False
    finally:
        if owned_root and work_root.exists():
            shutil.rmtree(work_root, ignore_errors=True)

    live_observations = (
        _blocked(
            "live_mcp_server",
            reason=mcp_server_probe.reason,
            limitations=("mcp_server_not_started",),
        ),
        _blocked(
            "live_ipfs_transport",
            reason=ipfs_probe.reason,
            limitations=(
                "ipfs_unavailable" if not ipfs_probe.present else "daemon_not_started",
            ),
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
        for operation in REQUIRED_PARITY_OPERATIONS
        if operation not in passed_ops
    )
    adapter_ops = tuple(
        _adapter_operation(
            item["operation"],
            status=str(item["status"]),
            reason=str(item.get("detail") or item.get("reason") or ""),
            digests=item.get("digests") if isinstance(item.get("digests"), Mapping) else {},
        )
        for item in observations
    )
    live_unavailable_ops = (
        _live_unavailable_operation("live_mcp_server", reason=mcp_server_probe.reason),
        _live_unavailable_operation("live_ipfs_transport", reason=ipfs_probe.reason),
    )
    contract = parity_contract()
    probes = (
        QualificationProbe(
            probe_id="interface_parity_surface",
            present=adapter_observed,
            evidence_kind="measured" if adapter_observed else "unavailable",
            live=False,
            simulated_represented_as_live=False,
            reason=(
                "AllInterfaceParityPolicy@1 python/cli/mcp/mcpp adapter sessions "
                "executed local-durable put/get/digest/delete against the live "
                "local POSIX store. Semantic payloads and CIDs matched. Live MCP "
                "server processes were not started."
                if adapter_observed
                else "Adapter parity suite failed closed."
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
                "is_hermetic": False,
                "live_provider": True,
                "surfaces": list(SURFACES),
                "operations": list(OPERATIONS),
                "live_mcp_server": False,
            },
        ),
        ipfs_probe,
        mcp_server_probe,
        *probe_surface_modules(),
        QualificationProbe(
            probe_id="sibling_test_tree_not_reopened",
            present=None,
            evidence_kind="unavailable",
            live=False,
            simulated_represented_as_live=False,
            reason=(
                "Sibling test-tree decoupling is "
                f"{PCPR_025_TASK_ID}. This receipt does not reopen it."
            ),
            details={"remediating_task": PCPR_025_TASK_ID},
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
    adapter_complete = adapter_observed and not missing
    disposition = (
        CertificationDisposition.CONDITIONAL.value
        if adapter_complete
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
        "interface_parity_live_qualified": False,
        "suite_complete": False,
        "certification_disposition": disposition,
        "support_class": SUPPORT_CLASS,
        "live_support_claim": False,
        "simulated_results_represented_as_live": False,
        "hermetic_results_represented_as_live": False,
        "adapter_parity_observed": adapter_complete,
        "interface_parity_qualified": adapter_complete,
        "live_server_parity_qualified": False,
        "live_ipfs_transport_qualified": False,
        "live_ipfs_evidence_kind": "unavailable",
        "this_task_created_competing_authority": False,
        "probes": [item.to_mapping() for item in probes],
        "observations": list(combined_observations),
        "adapter_operations": [dict(item) for item in adapter_ops],
        "live_unavailable_operations": [dict(item) for item in live_unavailable_ops],
        "operations_observed": list(passed_ops),
        "operations_missing": list(missing) + list(LIVE_UNAVAILABLE_OPERATIONS),
        "blockers": [],
        "policy": contract["policy"],
    }
    _reject_closed_release_value(payload["promotion_status"], "promotion_status")
    _reject_closed_release_value(
        payload["supervisor_disposition"], "supervisor_disposition"
    )
    if payload["closed_release_outcome"] is not None:
        raise InterfaceParityQualificationError("closed_release_outcome must be null")
    if payload["promotion_status"] not in PROMOTION_STATUSES:
        raise InterfaceParityQualificationError("promotion_status is not admitted")
    if payload["promotion_status"] == "supervisor_promoted":
        raise InterfaceParityQualificationError(
            "PCPR-026 cannot promote the supervisor"
        )
    if payload["interface_parity_live_qualified"] is True:
        raise InterfaceParityQualificationError(
            "interface_parity_live_qualified cannot be true without live MCP servers"
        )
    if payload["live_support_claim"] is True:
        raise InterfaceParityQualificationError(
            "live_support_claim cannot be true for PCPR-026"
        )
    if payload["live_server_parity_qualified"] is True:
        raise InterfaceParityQualificationError(
            "live_server_parity_qualified cannot be true without a live MCP server"
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
        interface_parity_live_qualified=False,
        suite_complete=False,
        certification_disposition=payload["certification_disposition"],
        support_class=SUPPORT_CLASS,
        live_support_claim=False,
        simulated_results_represented_as_live=False,
        hermetic_results_represented_as_live=False,
        adapter_parity_observed=bool(payload["adapter_parity_observed"]),
        interface_parity_qualified=bool(payload["interface_parity_qualified"]),
        live_server_parity_qualified=False,
        live_ipfs_transport_qualified=False,
        live_ipfs_evidence_kind="unavailable",
        this_task_created_competing_authority=False,
        probes=probes,
        observations=tuple(payload["observations"]),
        adapter_operations=tuple(payload["adapter_operations"]),
        live_unavailable_operations=tuple(payload["live_unavailable_operations"]),
        operations_observed=tuple(payload["operations_observed"]),
        operations_missing=tuple(payload["operations_missing"]),
        blockers=(),
        verdict_cid=cid,
    )


def qualify_current_head_interface_parity(
    *, now: datetime | None = None
) -> QualificationVerdict:
    return qualify_interface_parity(now=now)


def validate_pcpr_026_outer_receipt(payload: Mapping[str, Any]) -> None:
    """Reject closed-release claims and simulated-as-live promotion."""

    if not isinstance(payload, Mapping):
        raise InterfaceParityQualificationError("receipt must be a mapping")
    task_id = _text(payload.get("task_id"), "task_id")
    if task_id != PCPR_026_TASK_ID:
        raise InterfaceParityQualificationError("task_id must be PCPR-026")
    promotion = None
    acceptance = payload.get("acceptance")
    verdict = payload.get("qualification_verdict")
    if isinstance(acceptance, Mapping):
        promotion = acceptance.get("promotion_status")
        if acceptance.get("closed_release_outcome") is not None:
            raise InterfaceParityQualificationError(
                "acceptance.closed_release_outcome must be null"
            )
        if acceptance.get("release_claim") is True:
            raise InterfaceParityQualificationError(
                "acceptance.release_claim must be false"
            )
        if acceptance.get("interface_parity_live_qualified") is True:
            raise InterfaceParityQualificationError(
                "acceptance.interface_parity_live_qualified cannot be true without live MCP servers"
            )
    if isinstance(verdict, Mapping):
        promotion = verdict.get("promotion_status", promotion)
        if verdict.get("closed_release_outcome") is not None:
            raise InterfaceParityQualificationError(
                "qualification_verdict.closed_release_outcome must be null"
            )
        if verdict.get("interface_parity_live_qualified") is True:
            raise InterfaceParityQualificationError(
                "interface_parity_live_qualified cannot be true without live MCP servers"
            )
        if verdict.get("simulated_results_represented_as_live") is True:
            raise InterfaceParityQualificationError(
                "simulated results cannot be represented as live"
            )
        if verdict.get("hermetic_results_represented_as_live") is True:
            raise InterfaceParityQualificationError(
                "hermetic results cannot be represented as live"
            )
        if verdict.get("live_support_claim") is True:
            raise InterfaceParityQualificationError(
                "live_support_claim cannot be true without live evidence"
            )
        if verdict.get("live_server_parity_qualified") is True:
            raise InterfaceParityQualificationError(
                "live_server_parity_qualified cannot be true without a live MCP server"
            )
        live_kind = verdict.get("live_ipfs_evidence_kind")
        if live_kind is not None:
            _kind(live_kind, "live_ipfs_evidence_kind")
    promotion_text = _text(promotion, "promotion_status")
    if promotion_text not in PROMOTION_STATUSES:
        raise InterfaceParityQualificationError("promotion_status is not admitted")
    if promotion_text in CLOSED_RELEASE_OUTCOMES:
        raise InterfaceParityQualificationError(
            "promotion_status is a closed release outcome"
        )
    legend = payload.get("evidence_legend")
    if legend is not None and not isinstance(legend, Mapping):
        raise InterfaceParityQualificationError(
            "evidence_legend must be a mapping when present"
        )


def observe_pcpr_026_sealed_environment() -> dict[str, Any]:
    """Sealed PATH observation plus typed-unavailable extra tools."""

    measured = dict(observe_sealed_validation_environment())
    measured["fusermount"] = sealed_which("fusermount")
    measured["fusermount3"] = sealed_which("fusermount3")
    measured["docker"] = sealed_which("docker")
    measured["podman"] = sealed_which("podman")
    measured["iroh"] = sealed_which("iroh")
    measured["ipfs-kit-iroh-sidecar"] = sealed_which("ipfs-kit-iroh-sidecar")
    measured["dev_fuse"] = "/dev/fuse" if Path("/dev/fuse").exists() else "unavailable"
    try:
        import anyio  # type: ignore[import-untyped]

        anyio_file = getattr(anyio, "__file__", "") or ""
        if "/home/" in anyio_file or ".local" in anyio_file:
            measured["anyio"] = "unavailable"
        else:
            measured["anyio"] = anyio_file or "unavailable"
    except Exception:
        measured["anyio"] = "unavailable"
    return measured


__all__ = [
    "QUALIFICATION_INTERFACE",
    "QUALIFICATION_SCHEMA",
    "QUALIFICATION_VERDICT_SCHEMA",
    "PCPR_026_TASK_ID",
    "PCPR_026_GOAL_ID",
    "CLOSED_RELEASE_OUTCOMES",
    "PROMOTION_STATUSES",
    "HERMETIC_CANDIDATE_SUITES",
    "REQUIRED_PARITY_OPERATIONS",
    "LIVE_UNAVAILABLE_OPERATIONS",
    "InterfaceParityQualificationError",
    "QualificationVerdict",
    "sealed_which",
    "probe_live_ipfs_transport",
    "probe_live_mcp_server",
    "run_adapter_parity_suite",
    "qualify_interface_parity",
    "qualify_current_head_interface_parity",
    "validate_pcpr_026_outer_receipt",
    "observe_pcpr_026_sealed_environment",
    "observe_sealed_validation_environment",
]

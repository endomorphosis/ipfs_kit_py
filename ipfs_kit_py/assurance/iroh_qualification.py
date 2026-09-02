"""Fail-closed PCPR-022 Iroh qualification or honest de-scope.

PCPR-022 qualifies Iroh with the same bounded suite as pinned IPFS, or
classifies it experimental / unavailable / unsupported and removes
live-support claims. Live claims require a sealed-PATH
``ipfs-kit-iroh-sidecar`` binary plus an isolated provisioned sidecar.
Missing environments stay typed unavailable. Injected, hermetic, and
simulated transports cannot mint live qualification. CLI, MCP, and MCP++
parity remain typed unavailable until PCPR-026. Upgrade and rollback remain
typed unavailable until a digest-bound sidecar deployment exists.

This module is not release authority: it does not write DuckDB or Quack
state and never emits a closed PCPR release outcome.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final, Optional

from ipfs_kit_py.assurance.backend_certification import (
    REQUIRED_SUITE_OPERATIONS,
    CertificationDisposition,
    ObservationStatus,
    OperationObservation,
    contract_for,
    evaluate_observations,
    generate_suite,
)
from ipfs_kit_py.assurance.iroh import (
    BACKEND_ID,
    CERTIFICATION_SCOPE,
    INTERFACE as ADAPTER_INTERFACE,
    LARGE_OBJECT_BYTES,
    LIVE_SUPPORT_CLAIM,
    SCHEMA as ADAPTER_SCHEMA,
    SIDECAR_BINARY,
    SIDECAR_DIGEST,
    SIDECAR_PRODUCT,
    SIDECAR_VERSION,
    SUPPORT_CLASS,
    UPSTREAM_BINARY,
    IsolatedIrohSession,
    IrohBackendError,
    LiveIrohAdapter,
    provision_isolated_iroh_sidecar,
)
from ipfs_kit_py.assurance.local_backend_qualification import (
    CLOSED_RELEASE_OUTCOMES,
    EVIDENCE_KINDS,
    PROMOTION_STATUSES,
    SEALED_PATH,
    QualificationProbe,
    observe_sealed_validation_environment,
)
from ipfs_kit_py.core.operation_contracts import (
    ErrorCode,
    OperationState,
    content_identity,
)


QUALIFICATION_INTERFACE: Final = "IrohQualification@1"
QUALIFICATION_SCHEMA: Final = "ipfs_kit_py/assurance/iroh-qualification@1"
QUALIFICATION_VERDICT_SCHEMA: Final = (
    "ipfs_kit_py/assurance/iroh-qualification-verdict@1"
)

PCPR_022_TASK_ID: Final = "PCPR-022"
PCPR_022_GOAL_ID: Final = "PCPR-G300"
PCPR_021_TASK_ID: Final = "PCPR-021"
PCPR_020_TASK_ID: Final = "PCPR-020"
PCPR_003_TASK_ID: Final = "PCPR-003"
PCPR_001_TASK_ID: Final = "PCPR-001"
PCPR_023_TASK_ID: Final = "PCPR-023"
PCPR_026_TASK_ID: Final = "PCPR-026"
PCPR_027_TASK_ID: Final = "PCPR-027"
PCPR_PROGRAM_ID: Final = "proof-carrying-platform-qualification-and-release-v1"
PCPR_BOARD_NAMESPACE: Final = "proof-carrying-platform-qualification-and-release-v1"

PCPR_021_VERDICT_CID: Final = (
    "baguqeera73hiwlkjgzhkhaoazampvyq2zbu5jk4modig3ov6onbjy24n5vlq"
)
PCPR_020_VERDICT_CID: Final = (
    "baguqeeraxsfyay5pfotmvsb3ik3xkeog7tsvuwb6anrx75ld2vmllqqlwwcq"
)
PCPR_003_VERDICT_CID: Final = (
    "baguqeeraossnqpwfmgxwzhx4bmaaqdg2oiumoqujgxh2uz3dhzconolfepqa"
)

SECRET_PROBE: Final = "pcpr-022-do-not-retain-this-secret"
HERMETIC_CANDIDATE_SUITES: Final[tuple[str, ...]] = (
    "tests/test_pcpr_iroh_qualification.py",
)

IROH_SPECIFIC_OPERATIONS: Final[tuple[str, ...]] = (
    "clean_provisioning",
    "pin_persistence",
    "unpin_deletion",
    "daemon_loss",
    "unexpected_content",
    "configuration",
    "upgrade",
    "rollback",
)


class IrohQualificationError(ValueError):
    """Malformed qualification evidence or a forbidden authority claim."""


@dataclass(frozen=True)
class QualificationVerdict:
    """Fail-closed PCPR-022 Iroh decision. Never a closed release."""

    schema: str
    interface: str
    promotion_status: str
    supervisor_disposition: str
    closed_release_outcome: None
    release_claim: bool
    completion_authoritative: bool
    contracts_frozen: bool
    duckdb_or_quack_state_written: bool
    iroh_live_qualified: bool
    suite_complete: bool
    certification_disposition: str
    support_class: str
    live_support_claim: bool
    descoped: bool
    simulated_results_represented_as_live: bool
    hermetic_results_represented_as_live: bool
    python_iroh_observed: bool
    interface_parity_qualified: bool
    sealed_iroh_sidecar: str
    sealed_iroh_binary: str
    sidecar_identity: str
    live_iroh_evidence_kind: str
    this_task_created_competing_authority: bool
    probes: tuple[QualificationProbe, ...]
    observations: tuple[dict[str, Any], ...]
    iroh_operations: tuple[dict[str, Any], ...]
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
            "iroh_live_qualified": self.iroh_live_qualified,
            "suite_complete": self.suite_complete,
            "certification_disposition": self.certification_disposition,
            "support_class": self.support_class,
            "live_support_claim": self.live_support_claim,
            "descoped": self.descoped,
            "simulated_results_represented_as_live": (
                self.simulated_results_represented_as_live
            ),
            "hermetic_results_represented_as_live": (
                self.hermetic_results_represented_as_live
            ),
            "python_iroh_observed": self.python_iroh_observed,
            "interface_parity_qualified": self.interface_parity_qualified,
            "sealed_iroh_sidecar": self.sealed_iroh_sidecar,
            "sealed_iroh_binary": self.sealed_iroh_binary,
            "sidecar_identity": self.sidecar_identity,
            "live_iroh_evidence_kind": self.live_iroh_evidence_kind,
            "this_task_created_competing_authority": (
                self.this_task_created_competing_authority
            ),
            "probes": [item.to_mapping() for item in self.probes],
            "observations": [dict(item) for item in self.observations],
            "iroh_operations": [dict(item) for item in self.iroh_operations],
            "operations_observed": list(self.operations_observed),
            "operations_missing": list(self.operations_missing),
            "blockers": list(self.blockers),
            "verdict_cid": self.verdict_cid,
        }


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IrohQualificationError(f"{name} must be a non-empty string")
    return value.strip()


def _kind(value: Any, name: str) -> str:
    kind = _text(value, name)
    if kind not in EVIDENCE_KINDS:
        raise IrohQualificationError(f"{name} is not an admitted evidence kind")
    return kind


def _reject_closed_release_value(value: Any, name: str) -> None:
    if isinstance(value, str) and value in CLOSED_RELEASE_OUTCOMES:
        raise IrohQualificationError(
            f"{name} must not be a closed PCPR release outcome"
        )


def _observation_mapping(item: OperationObservation) -> dict[str, Any]:
    return {
        "operation": item.operation,
        "status": item.status.value,
        "environment": item.environment,
        "source": item.source,
        "signature_valid": item.signature_valid,
        "freshness": item.freshness,
        "digests": dict(item.digests),
        "limitations": list(item.limitations),
        "detail": item.detail,
    }


def _unobserved(operation: str, reason: str) -> OperationObservation:
    return OperationObservation(
        operation=operation,
        status=ObservationStatus.UNOBSERVED,
        environment="live",
        source="unavailable",
        signature_valid=False,
        freshness="missing",
        digests={"reason": reason},
        limitations=("sidecar_unavailable",),
        detail=reason,
    )


def _passed(
    operation: str,
    *,
    digests: Mapping[str, str],
    limitations: tuple[str, ...] = (),
    detail: str | None = None,
) -> OperationObservation:
    return OperationObservation(
        operation=operation,
        status=ObservationStatus.PASSED,
        environment="live",
        source="live_observed",
        signature_valid=True,
        freshness="current",
        digests=dict(digests),
        limitations=limitations,
        detail=detail,
    )


def _blocked(
    operation: str,
    *,
    reason: str,
    limitations: tuple[str, ...] = (),
) -> OperationObservation:
    return OperationObservation(
        operation=operation,
        status=ObservationStatus.BLOCKED,
        environment="live",
        source="unavailable",
        signature_valid=False,
        freshness="missing",
        digests={"reason": reason},
        limitations=limitations,
        detail=reason,
    )


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _iroh_operation(
    operation: str,
    *,
    status: str,
    evidence_kind: str,
    reason: str,
    live: bool = False,
) -> dict[str, Any]:
    return {
        "operation": operation,
        "status": status,
        "environment": "live",
        "source": "live_observed" if live else "unavailable",
        "evidence_kind": evidence_kind,
        "live": live,
        "simulated_represented_as_live": False,
        "reason": reason,
    }


def refuse_simulated_as_live(adapter: Any) -> None:
    """Hermetic, simulated, or injected adapters cannot mint live evidence."""

    live_provider = bool(getattr(adapter, "live_provider", False))
    hermetic = bool(getattr(adapter, "is_hermetic", True))
    simulated = bool(getattr(adapter, "simulated", False))
    transport_kind = str(getattr(adapter, "transport_kind", ""))
    if hermetic or simulated or not live_provider or transport_kind != "unix-rpc":
        raise IrohQualificationError(
            "hermetic, simulated, or injected adapters cannot mint live "
            "Iroh qualification"
        )
    if getattr(adapter, "backend_id", None) != BACKEND_ID:
        raise IrohQualificationError(
            "live Iroh qualification requires backend_id='iroh'"
        )
    if getattr(adapter, "live_support_claim", True) is True:
        raise IrohQualificationError(
            "an adapter cannot mint a live-support claim without a complete "
            "live observed suite"
        )


def sealed_which(name: str) -> str:
    """Resolve an executable on the sealed validation PATH only."""

    for directory in SEALED_PATH.split(":"):
        candidate = Path(directory) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return "unavailable"


def probe_sealed_iroh_sidecar() -> QualificationProbe:
    path = sealed_which(SIDECAR_BINARY)
    present = path != "unavailable"
    return QualificationProbe(
        probe_id="sealed_iroh_sidecar",
        present=present,
        evidence_kind="measured" if present else "unavailable",
        live=False,
        simulated_represented_as_live=False,
        reason=(
            f"Sealed PATH {SIDECAR_BINARY} is {path}."
            if present
            else (
                "Sealed validation PATH has no ipfs-kit-iroh-sidecar executable. "
                "A digest-bound Iroh sidecar was not provisioned. Missing sidecar "
                "evidence stays typed unavailable and is not recorded as zero or "
                "passing. Iroh is classified experimental and is not live-supported."
            )
        ),
        details={
            "binary": SIDECAR_BINARY,
            "product": SIDECAR_PRODUCT,
            "path": path,
            "PATH": SEALED_PATH,
            "auto_install": False,
            "support_class": SUPPORT_CLASS,
            "live_support_claim": LIVE_SUPPORT_CLAIM,
        },
    )


def probe_sealed_iroh_binary() -> QualificationProbe:
    path = sealed_which(UPSTREAM_BINARY)
    present = path != "unavailable"
    return QualificationProbe(
        probe_id="sealed_iroh_binary",
        present=present,
        evidence_kind="measured" if present else "unavailable",
        live=False,
        simulated_represented_as_live=False,
        reason=(
            f"Sealed PATH {UPSTREAM_BINARY} is {path}. Upstream iroh is not "
            "the Kit sidecar runtime."
            if present
            else (
                "Sealed validation PATH has no upstream iroh executable. "
                "Upstream iroh is not the Kit sidecar runtime and is not live "
                "qualification. Missing binary stays typed unavailable."
            )
        ),
        details={
            "binary": UPSTREAM_BINARY,
            "product": SIDECAR_PRODUCT,
            "path": path,
            "PATH": SEALED_PATH,
            "decision": "not-a-backend-runtime",
        },
    )


def probe_sidecar_identity() -> QualificationProbe:
    return QualificationProbe(
        probe_id="sidecar_identity",
        present=False,
        evidence_kind="unavailable",
        live=False,
        simulated_represented_as_live=False,
        reason=(
            "No digest-bound ipfs-kit-iroh-sidecar deployment is present on "
            f"the sealed PATH. Declared pin version={SIDECAR_VERSION} "
            f"digest={SIDECAR_DIGEST}. Packaged crate checksums and "
            "iroh-releases.json configuration are not live identity."
        ),
        details={
            "product": SIDECAR_PRODUCT,
            "binary": SIDECAR_BINARY,
            "version": SIDECAR_VERSION,
            "digest": SIDECAR_DIGEST,
        },
    )


def probe_auto_install_not_used() -> QualificationProbe:
    env_value = os.environ.get("IPFS_KIT_AUTO_INSTALL_BINARIES")
    return QualificationProbe(
        probe_id="auto_install_not_used",
        present=False,
        evidence_kind="measured",
        live=False,
        simulated_represented_as_live=False,
        reason=(
            "PCPR-022 never calls install_iroh or IrohInstallManager with "
            "install=True and never downloads a sidecar. Missing sidecar "
            "stays typed unavailable."
        ),
        details={
            "IPFS_KIT_AUTO_INSTALL_BINARIES": env_value if env_value else "unset",
            "install_invoked": False,
        },
    )


def probe_live_support_removed() -> QualificationProbe:
    return QualificationProbe(
        probe_id="live_support_claim_removed",
        present=False,
        evidence_kind="measured",
        live=False,
        simulated_represented_as_live=False,
        reason=(
            "Iroh is classified experimental. Live-support claims are removed. "
            "Disabled-by-default packaging and installable:false platforms are "
            "not live qualification. Configuration is not live qualification."
        ),
        details={
            "support_class": SUPPORT_CLASS,
            "live_support_claim": False,
            "production_authorized": False,
            "descoped": True,
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
                f"No live Iroh {surface} session was exercised. "
                f"Parity remains typed unavailable until {remediating}."
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
                probe_id=f"{surface}_iroh_parity",
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


def unavailable_required_observations(reason: str) -> tuple[OperationObservation, ...]:
    return tuple(_unobserved(operation, reason) for operation in REQUIRED_SUITE_OPERATIONS)


def unavailable_iroh_operations(reason: str) -> tuple[dict[str, Any], ...]:
    return tuple(
        _iroh_operation(
            operation,
            status="unobserved",
            evidence_kind="unavailable",
            reason=reason,
        )
        for operation in IROH_SPECIFIC_OPERATIONS
    )


def run_live_iroh_suite(
    adapter: LiveIrohAdapter,
    session: IsolatedIrohSession | None = None,
) -> tuple[tuple[OperationObservation, ...], tuple[dict[str, Any], ...]]:
    """Execute the required Iroh suite against a live sidecar.

    The caller must have provisioned an isolated sidecar. CLI/MCP/MCP++
    parity, upgrade, and rollback stay blocked/unavailable.
    """

    refuse_simulated_as_live(adapter)
    observations: list[OperationObservation] = []
    extras: list[dict[str, Any]] = []

    payload = b"pcpr-022-iroh-write-v1"
    written = adapter.add(payload, pin=True, idempotency_key="write-1")
    assert written.success is True
    assert len(written.resulting_content_cid) == 64
    observations.append(
        _passed(
            "write",
            digests={
                "blob_hash": written.resulting_content_cid,
                "bytes": f"sha256:{_sha256_hex(payload)}",
            },
        )
    )

    read_back = adapter.cat(
        written.resulting_content_cid, expected_blake3=written.resulting_content_cid
    )
    assert read_back.data == payload
    assert read_back.resulting_content_cid == written.resulting_content_cid
    observations.append(
        _passed(
            "read_back",
            digests={
                "blob_hash": read_back.resulting_content_cid,
                "bytes": f"sha256:{_sha256_hex(read_back.data)}",
            },
        )
    )

    digested = adapter.digest(written.resulting_content_cid)
    assert digested.resulting_content_cid == written.resulting_content_cid
    observations.append(
        _passed(
            "digest",
            digests={
                "blob_hash": digested.resulting_content_cid,
                "algorithm": "blake3",
            },
        )
    )

    extras.append(
        _iroh_operation(
            "pin_persistence",
            status="passed",
            evidence_kind="measured_live",
            reason="blob remained protected after ingest+protect.",
            live=True,
        )
    )

    deleted = adapter.delete(written.resulting_content_cid, idempotency_key="delete-1")
    assert deleted.success is True
    replay_delete = adapter.delete(
        written.resulting_content_cid, idempotency_key="delete-1"
    )
    assert replay_delete.resulting_content_cid == deleted.resulting_content_cid
    observations.append(
        _passed(
            "delete",
            digests={
                "blob_hash": deleted.resulting_content_cid,
                "replay_delete_safe": "true",
            },
        )
    )
    extras.append(
        _iroh_operation(
            "unpin_deletion",
            status="passed",
            evidence_kind="measured_live",
            reason="blobs.release completed; replay delete was safe.",
            live=True,
        )
    )

    replay_payload = b"pcpr-022-replay"
    first = adapter.add(replay_payload, idempotency_key="replay-1")
    effects_after_first = adapter.effect_count
    second = adapter.add(replay_payload, idempotency_key="replay-1")
    assert second.resulting_content_cid == first.resulting_content_cid
    assert adapter.effect_count == effects_after_first
    try:
        adapter.add(b"other", idempotency_key="replay-1")
    except IrohBackendError as exc:
        assert exc.error.code is ErrorCode.CONFLICT
    else:
        raise IrohQualificationError("idempotency conflict was not raised")
    observations.append(
        _passed(
            "replay",
            digests={
                "blob_hash": first.resulting_content_cid,
                "effect_count_stable": str(effects_after_first),
            },
        )
    )

    past = time.monotonic() - 5
    try:
        adapter.add(b"too-late", deadline=past)
    except IrohBackendError as exc:
        assert exc.error.code is ErrorCode.DEADLINE_EXCEEDED
        assert exc.error.state is OperationState.DEADLINE_EXCEEDED
    else:
        raise IrohQualificationError("past deadline was not honored")
    cancelled = threading.Event()
    cancelled.set()
    try:
        adapter.add(b"cancelled", cancel_event=cancelled)
    except IrohBackendError as exc:
        assert exc.error.code is ErrorCode.CANCELLED
    else:
        raise IrohQualificationError("cancellation was not honored")
    observations.append(
        _passed(
            "timeout",
            digests={
                "deadline_exceeded": ErrorCode.DEADLINE_EXCEEDED.value,
                "cancelled": ErrorCode.CANCELLED.value,
            },
        )
    )

    collected: list[str] = []

    def _worker(index: int) -> None:
        body = f"pcpr-022-worker-{index}".encode("ascii")
        result = adapter.add(body, pin=True)
        got = adapter.cat(result.resulting_content_cid)
        if got.data != body:
            raise IrohQualificationError(f"concurrency corruption at {index}")
        collected.append(result.resulting_content_cid)

    threads = [threading.Thread(target=_worker, args=(index,)) for index in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    if len(collected) != 4:
        raise IrohQualificationError("concurrency workers did not complete")
    observations.append(
        _passed(
            "concurrency",
            digests={
                "workers": "4",
                "combined": "sha256:"
                + _sha256_hex("".join(sorted(collected)).encode("ascii")),
            },
        )
    )

    durable_payload = b"pcpr-022-restart-durable"
    durable = adapter.add(durable_payload, pin=True)
    adapter.close()
    reopened = LiveIrohAdapter(adapter.endpoint)
    refuse_simulated_as_live(reopened)
    restored = reopened.cat(durable.resulting_content_cid)
    if restored.data != durable_payload:
        raise IrohQualificationError("restart lost durable bytes")
    observations.append(
        _passed(
            "restart",
            digests={
                "blob_hash": restored.resulting_content_cid,
                "bytes": f"sha256:{_sha256_hex(restored.data)}",
            },
            detail="new adapter instance against the same provisioned sidecar",
        )
    )
    extras.append(
        _iroh_operation(
            "clean_provisioning",
            status="passed" if session is not None else "unobserved",
            evidence_kind="measured_live" if session is not None else "unavailable",
            reason=(
                "Isolated Iroh sidecar was provisioned for this suite."
                if session is not None
                else "Suite ran against a caller-supplied sidecar; clean provisioning was not independently started here."
            ),
            live=session is not None,
        )
    )
    extras.append(
        _iroh_operation(
            "configuration",
            status="passed" if session is not None else "unobserved",
            evidence_kind="measured_live" if session is not None else "unavailable",
            reason=(
                "Isolated state root with local-only RPC bind was recorded."
                if session is not None
                else "No isolated configuration was provisioned by this runner."
            ),
            live=session is not None,
        )
    )

    unexpected = b"pcpr-022-unexpected"
    unexpected_put = reopened.add(unexpected, pin=True)
    try:
        reopened.cat(unexpected_put.resulting_content_cid, expected_blake3="00" * 32)
    except IrohBackendError as exc:
        assert exc.error.code is ErrorCode.INTEGRITY_FAILURE
    else:
        raise IrohQualificationError("unexpected content was not detected")
    observations.append(
        _passed(
            "corruption",
            digests={
                "expected_hash": unexpected_put.resulting_content_cid,
                "detected": ErrorCode.INTEGRITY_FAILURE.value,
            },
            detail="expected BLAKE3 mismatch failed closed",
        )
    )
    extras.append(
        _iroh_operation(
            "unexpected_content",
            status="passed",
            evidence_kind="measured_live",
            reason="cat with a forged expected digest failed closed as integrity failure.",
            live=True,
        )
    )

    large_payload = (b"ABCDEFGH" * (LARGE_OBJECT_BYTES // 8))[:LARGE_OBJECT_BYTES]
    large = reopened.add(large_payload, pin=True)
    large_read = reopened.cat(large.resulting_content_cid)
    if large_read.data != large_payload or len(large_read.data) != LARGE_OBJECT_BYTES:
        raise IrohQualificationError("large object round-trip failed")
    observations.append(
        _passed(
            "large_object",
            digests={
                "size": str(len(large_read.data)),
                "blob_hash": large.resulting_content_cid,
                "bytes": f"sha256:{_sha256_hex(large_read.data)}",
            },
        )
    )

    try:
        LiveIrohAdapter(configuration={"api_token": SECRET_PROBE})
    except IrohBackendError as exc:
        assert exc.error.code is ErrorCode.SECRET_MATERIAL
        if SECRET_PROBE in str(exc):
            raise IrohQualificationError("secret material leaked in error")
    else:
        raise IrohQualificationError("secret configuration was not rejected")
    try:
        reopened.add(b"nope", metadata={"password": SECRET_PROBE})
    except IrohBackendError as exc:
        assert exc.error.code is ErrorCode.SECRET_MATERIAL
    else:
        raise IrohQualificationError("secret metadata was not rejected")
    observations.append(
        _passed(
            "credential",
            digests={
                "raw_material_rejected": ErrorCode.SECRET_MATERIAL.value,
                "material_absent_from_receipts": "true",
            },
            limitations=("no_credentials_required",),
        )
    )

    observations.append(
        _blocked(
            "interface_parity",
            reason=(
                "Python Iroh ingest/cat/digest/protect/release were live-observed. "
                "CLI, MCP, and MCP++ Iroh sessions were not exercised. "
                f"{PCPR_026_TASK_ID} owns interface parity."
            ),
            limitations=(
                "python_live_observed",
                "cli_unavailable",
                "mcp_unavailable",
                "mcpp_unavailable",
            ),
        )
    )

    extras.append(
        _iroh_operation(
            "upgrade",
            status="unobserved",
            evidence_kind="unavailable",
            reason=(
                "No digest-bound Iroh sidecar upgrade package is present on the "
                "sealed PATH. Upgrade stays typed unavailable."
            ),
        )
    )
    extras.append(
        _iroh_operation(
            "rollback",
            status="unobserved",
            evidence_kind="unavailable",
            reason=(
                "No digest-bound Iroh sidecar rollback package is present on the "
                "sealed PATH. Rollback stays typed unavailable."
            ),
        )
    )

    if session is not None:
        session.stop()
        try:
            reopened.health()
        except IrohBackendError as exc:
            assert exc.error.code is ErrorCode.UNAVAILABLE
            extras.append(
                _iroh_operation(
                    "daemon_loss",
                    status="passed",
                    evidence_kind="measured_live",
                    reason="After stopping the provisioned sidecar, health failed closed as unavailable.",
                    live=True,
                )
            )
        else:
            raise IrohQualificationError("sidecar loss was not detected")
    else:
        extras.append(
            _iroh_operation(
                "daemon_loss",
                status="unobserved",
                evidence_kind="unavailable",
                reason="Sidecar loss was not exercised because this runner did not own the sidecar process.",
            )
        )

    observed_ops = {item.operation for item in observations}
    if observed_ops != set(REQUIRED_SUITE_OPERATIONS):
        raise IrohQualificationError(
            f"suite operations mismatch: {sorted(observed_ops)}"
        )
    extra_ops = {item["operation"] for item in extras}
    if extra_ops != set(IROH_SPECIFIC_OPERATIONS):
        raise IrohQualificationError(
            f"iroh-specific operations mismatch: {sorted(extra_ops)}"
        )
    reopened.close()
    return tuple(observations), tuple(extras)


def evaluate_iroh(
    observations: Sequence[OperationObservation],
    *,
    live_runner_present: bool,
    now: datetime | None = None,
) -> Any:
    contract = contract_for(BACKEND_ID)
    suite = generate_suite(contract, now=now)
    return evaluate_observations(
        contract,
        observations if live_runner_present else (),
        live_runner_present=live_runner_present,
        now=now,
        suite=suite,
    )


def _verdict_cid(payload: Mapping[str, Any]) -> str:
    body = {key: payload[key] for key in payload if key != "verdict_cid"}
    return content_identity(body)


def qualify_iroh(
    *,
    now: datetime | None = None,
    force_unavailable: bool = False,
) -> QualificationVerdict:
    """Qualify Iroh or issue an honest experimental/unavailable R&D verdict."""

    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        raise IrohQualificationError("now must be timezone-aware")

    sidecar_probe = probe_sealed_iroh_sidecar()
    upstream_probe = probe_sealed_iroh_binary()
    identity_probe = probe_sidecar_identity()
    auto_install_probe = probe_auto_install_not_used()
    live_support_probe = probe_live_support_removed()
    sidecar_path = sidecar_probe.details.get("path", "unavailable")
    upstream_path = upstream_probe.details.get("path", "unavailable")
    live_runner = sidecar_path != "unavailable" and not force_unavailable

    session: IsolatedIrohSession | None = None
    observations: tuple[OperationObservation, ...]
    extras: tuple[dict[str, Any], ...]
    python_observed = False
    live_kind = "unavailable"
    work_root: Path | None = None

    if live_runner:
        work_root = Path(tempfile.mkdtemp(prefix="pcpr-022-iroh-"))
        try:
            session = provision_isolated_iroh_sidecar(
                sidecar_binary=sidecar_path,
                state_root=work_root / "state",
            )
            adapter = LiveIrohAdapter(session.endpoint)
            observations, extras = run_live_iroh_suite(adapter, session=session)
            python_observed = True
            live_kind = "measured_live"
        except (IrohBackendError, IrohQualificationError) as exc:
            reason = (
                "Sealed ipfs-kit-iroh-sidecar was present but isolated sidecar "
                f"provisioning or the live suite failed closed: {exc}."
            )
            observations = unavailable_required_observations(reason)
            extras = unavailable_iroh_operations(reason)
            live_runner = False
            live_kind = "unavailable"
            python_observed = False
        finally:
            if session is not None:
                try:
                    session.stop()
                except Exception:
                    pass
            if work_root is not None and work_root.exists():
                shutil.rmtree(work_root, ignore_errors=True)
    else:
        reason = (
            "Sealed validation PATH has no ipfs-kit-iroh-sidecar executable and "
            "no digest-bound Iroh deployment. Isolated sidecar provisioning was "
            "not attempted. Missing sidecar evidence stays typed unavailable. "
            "Iroh is classified experimental; live-support claims are removed."
        )
        observations = unavailable_required_observations(reason)
        extras = unavailable_iroh_operations(reason)

    result = evaluate_iroh(
        observations,
        live_runner_present=live_runner and python_observed,
        now=reference,
    )
    if result.live_qualified:
        raise IrohQualificationError(
            "PCPR-022 must not mint LiveQualified while the sidecar "
            "identity, interface parity, upgrade, or rollback remain incomplete"
        )
    if result.disposition is CertificationDisposition.LIVE_QUALIFIED:
        raise IrohQualificationError(
            "certification disposition LiveQualified is forbidden for PCPR-022"
        )

    if python_observed:
        live_probe = QualificationProbe(
            probe_id="live_iroh_adapter",
            present=True,
            evidence_kind="measured_live",
            live=True,
            simulated_represented_as_live=False,
            reason=(
                "LiveIrohAdapter executed ingest, cat, digest, protect, release, "
                "delete, replay, timeout, concurrency, restart, unexpected "
                "content, large-object, and credential cases against an "
                "isolated provisioned Iroh sidecar."
            ),
            details={
                "backend_id": BACKEND_ID,
                "schema": ADAPTER_SCHEMA,
                "interface": ADAPTER_INTERFACE,
                "certification_scope": CERTIFICATION_SCOPE,
                "production_authorized": False,
                "live_support_claim": False,
            },
        )
    else:
        live_probe = QualificationProbe(
            probe_id="live_iroh_adapter",
            present=False,
            evidence_kind="unavailable",
            live=False,
            simulated_represented_as_live=False,
            reason=(
                "No isolated Iroh sidecar was provisioned. "
                "LiveIrohAdapter was not used as live evidence. Iroh remains "
                "experimental and is not live-supported."
            ),
            details={
                "backend_id": BACKEND_ID,
                "schema": ADAPTER_SCHEMA,
                "interface": ADAPTER_INTERFACE,
                "certification_scope": CERTIFICATION_SCOPE,
                "production_authorized": False,
                "live_support_claim": False,
                "support_class": SUPPORT_CLASS,
            },
        )

    probes = (
        live_probe,
        sidecar_probe,
        upstream_probe,
        identity_probe,
        auto_install_probe,
        live_support_probe,
        *probe_cli_mcp_surfaces(),
        QualificationProbe(
            probe_id="vfs_wal_not_in_scope",
            present=None,
            evidence_kind="unavailable",
            live=False,
            simulated_represented_as_live=False,
            reason=(
                f"VFS/WAL/current-root recovery is {PCPR_023_TASK_ID}. Missing "
                "VFS evidence stays typed unavailable."
            ),
            details={"remediating_task": PCPR_023_TASK_ID},
        ),
        QualificationProbe(
            probe_id="support_matrix_not_generated",
            present=False,
            evidence_kind="unavailable",
            live=False,
            simulated_represented_as_live=False,
            reason=(
                f"Authoritative support-matrix generation is {PCPR_027_TASK_ID}. "
                "This receipt does not replace it."
            ),
            details={"remediating_task": PCPR_027_TASK_ID},
        ),
    )

    python_ops = tuple(
        item.operation
        for item in observations
        if item.status is ObservationStatus.PASSED
    )
    missing = tuple(result.operations_missing) if result.operations_missing else tuple(
        REQUIRED_SUITE_OPERATIONS
    )
    disposition = result.disposition.value
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
        "iroh_live_qualified": False,
        "suite_complete": False,
        "certification_disposition": disposition,
        "support_class": SUPPORT_CLASS,
        "live_support_claim": False,
        "descoped": not python_observed,
        "simulated_results_represented_as_live": False,
        "hermetic_results_represented_as_live": False,
        "python_iroh_observed": python_observed
        and set(python_ops)
        >= {
            "write",
            "read_back",
            "digest",
            "delete",
            "replay",
            "timeout",
            "concurrency",
            "restart",
            "corruption",
            "large_object",
            "credential",
        },
        "interface_parity_qualified": False,
        "sealed_iroh_sidecar": sidecar_path,
        "sealed_iroh_binary": upstream_path,
        "sidecar_identity": SIDECAR_DIGEST,
        "live_iroh_evidence_kind": live_kind,
        "this_task_created_competing_authority": False,
        "probes": [item.to_mapping() for item in probes],
        "observations": [_observation_mapping(item) for item in observations],
        "iroh_operations": [dict(item) for item in extras],
        "operations_observed": list(result.operations_observed),
        "operations_missing": list(missing),
        "blockers": [],
    }
    _reject_closed_release_value(payload["promotion_status"], "promotion_status")
    _reject_closed_release_value(
        payload["supervisor_disposition"], "supervisor_disposition"
    )
    if payload["closed_release_outcome"] is not None:
        raise IrohQualificationError("closed_release_outcome must be null")
    if payload["promotion_status"] not in PROMOTION_STATUSES:
        raise IrohQualificationError("promotion_status is not admitted")
    if payload["promotion_status"] == "supervisor_promoted":
        raise IrohQualificationError("PCPR-022 cannot promote the supervisor")
    if payload["iroh_live_qualified"] is True:
        raise IrohQualificationError(
            "iroh_live_qualified cannot be true while the suite is incomplete"
        )
    if payload["live_support_claim"] is True:
        raise IrohQualificationError("live_support_claim cannot be true for PCPR-022")
    cid = _verdict_cid(payload)
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
        iroh_live_qualified=False,
        suite_complete=False,
        certification_disposition=payload["certification_disposition"],
        support_class=str(payload["support_class"]),
        live_support_claim=False,
        descoped=bool(payload["descoped"]),
        simulated_results_represented_as_live=False,
        hermetic_results_represented_as_live=False,
        python_iroh_observed=bool(payload["python_iroh_observed"]),
        interface_parity_qualified=False,
        sealed_iroh_sidecar=str(payload["sealed_iroh_sidecar"]),
        sealed_iroh_binary=str(payload["sealed_iroh_binary"]),
        sidecar_identity=str(payload["sidecar_identity"]),
        live_iroh_evidence_kind=str(payload["live_iroh_evidence_kind"]),
        this_task_created_competing_authority=False,
        probes=probes,
        observations=tuple(payload["observations"]),
        iroh_operations=tuple(payload["iroh_operations"]),
        operations_observed=tuple(payload["operations_observed"]),
        operations_missing=tuple(payload["operations_missing"]),
        blockers=(),
        verdict_cid=cid,
    )


def qualify_current_head_iroh(
    *, now: datetime | None = None
) -> QualificationVerdict:
    return qualify_iroh(now=now)


def validate_pcpr_022_outer_receipt(payload: Mapping[str, Any]) -> None:
    """Reject closed-release claims and simulated-as-live promotion."""

    if not isinstance(payload, Mapping):
        raise IrohQualificationError("receipt must be a mapping")
    task_id = _text(payload.get("task_id"), "task_id")
    if task_id != PCPR_022_TASK_ID:
        raise IrohQualificationError("task_id must be PCPR-022")
    promotion = None
    acceptance = payload.get("acceptance")
    verdict = payload.get("qualification_verdict")
    if isinstance(acceptance, Mapping):
        promotion = acceptance.get("promotion_status")
        if acceptance.get("closed_release_outcome") is not None:
            raise IrohQualificationError(
                "acceptance.closed_release_outcome must be null"
            )
        if acceptance.get("release_claim") is True:
            raise IrohQualificationError("acceptance.release_claim must be false")
        if acceptance.get("live_support_claim") is True:
            raise IrohQualificationError("acceptance.live_support_claim must be false")
    if isinstance(verdict, Mapping):
        promotion = verdict.get("promotion_status", promotion)
        if verdict.get("closed_release_outcome") is not None:
            raise IrohQualificationError(
                "qualification_verdict.closed_release_outcome must be null"
            )
        if verdict.get("iroh_live_qualified") is True:
            raise IrohQualificationError(
                "iroh_live_qualified cannot be true while the suite is incomplete"
            )
        if verdict.get("simulated_results_represented_as_live") is True:
            raise IrohQualificationError(
                "simulated results cannot be represented as live"
            )
        if verdict.get("live_support_claim") is True:
            raise IrohQualificationError(
                "live_support_claim cannot be true without a complete live suite"
            )
        live_kind = verdict.get("live_iroh_evidence_kind")
        if live_kind is not None:
            _kind(live_kind, "live_iroh_evidence_kind")
    promotion_text = _text(promotion, "promotion_status")
    if promotion_text not in PROMOTION_STATUSES:
        raise IrohQualificationError("promotion_status is not admitted")
    if promotion_text in CLOSED_RELEASE_OUTCOMES:
        raise IrohQualificationError("promotion_status is a closed release outcome")
    legend = payload.get("evidence_legend")
    if legend is not None and not isinstance(legend, Mapping):
        raise IrohQualificationError(
            "evidence_legend must be a mapping when present"
        )


__all__ = [
    "QUALIFICATION_INTERFACE",
    "QUALIFICATION_SCHEMA",
    "QUALIFICATION_VERDICT_SCHEMA",
    "PCPR_022_TASK_ID",
    "PCPR_022_GOAL_ID",
    "CLOSED_RELEASE_OUTCOMES",
    "PROMOTION_STATUSES",
    "HERMETIC_CANDIDATE_SUITES",
    "IROH_SPECIFIC_OPERATIONS",
    "IrohQualificationError",
    "QualificationVerdict",
    "refuse_simulated_as_live",
    "sealed_which",
    "probe_sealed_iroh_sidecar",
    "run_live_iroh_suite",
    "evaluate_iroh",
    "qualify_iroh",
    "qualify_current_head_iroh",
    "validate_pcpr_022_outer_receipt",
    "observe_sealed_validation_environment",
]

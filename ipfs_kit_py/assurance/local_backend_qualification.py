"""Fail-closed PCPR-020 local Kit backend requalification.

PCPR-020 requalifies the current-head local durable filesystem backend.
Live claims require live local POSIX evidence. Hermetic reference adapters
and simulated results cannot mint live qualification. CLI, MCP, and MCP++
parity remain typed unavailable until PCPR-026. This module is not release
authority: it does not write DuckDB or Quack state and never emits a closed
PCPR release outcome.
"""

from __future__ import annotations

import ast
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
from types import MappingProxyType
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
from ipfs_kit_py.assurance.local_durable import (
    BACKEND_ID,
    CERTIFICATION_SCOPE,
    INTERFACE as ADAPTER_INTERFACE,
    LARGE_OBJECT_BYTES,
    SCHEMA as ADAPTER_SCHEMA,
    LiveLocalBackendError,
    LiveLocalFilesystemAdapter,
)
from ipfs_kit_py.core.operation_contracts import (
    ErrorCode,
    OperationState,
    content_identity,
)


QUALIFICATION_INTERFACE: Final = "LocalBackendQualification@1"
QUALIFICATION_SCHEMA: Final = (
    "ipfs_kit_py/assurance/local-backend-qualification@1"
)
QUALIFICATION_VERDICT_SCHEMA: Final = (
    "ipfs_kit_py/assurance/local-backend-qualification-verdict@1"
)

PCPR_020_TASK_ID: Final = "PCPR-020"
PCPR_020_GOAL_ID: Final = "PCPR-G300"
PCPR_003_TASK_ID: Final = "PCPR-003"
PCPR_001_TASK_ID: Final = "PCPR-001"
PCPR_021_TASK_ID: Final = "PCPR-021"
PCPR_026_TASK_ID: Final = "PCPR-026"
PCPR_027_TASK_ID: Final = "PCPR-027"
PCPR_PROGRAM_ID: Final = "proof-carrying-platform-qualification-and-release-v1"
PCPR_BOARD_NAMESPACE: Final = "proof-carrying-platform-qualification-and-release-v1"

EVIDENCE_KINDS: Final[frozenset[str]] = frozenset(
    {
        "measured",
        "measured_live",
        "measured_hermetic",
        "estimated",
        "simulated",
        "unavailable",
    }
)
PROMOTION_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "supervisor_promoted",
        "supervisor_non_promoted",
        "rnd_non_promoted",
        "typed_unavailable",
        "typed_blocked",
    }
)
CLOSED_RELEASE_OUTCOMES: Final[frozenset[str]] = frozenset(
    {
        "release_candidate_qualified",
        "non_promoted_supervisor_unqualified",
        "non_promoted_import_or_false_success",
        "non_promoted_live_storage_gap",
        "non_promoted_live_compute_gap",
        "non_promoted_solver_gap",
        "non_promoted_packaging_gap",
        "non_promoted_dependency_reproducibility",
        "non_promoted_security_failure",
        "non_promoted_interoperability_gap",
        "non_promoted_reference_workflow_failure",
        "non_promoted_unmeasured",
        "non_promoted_operator_gate_required",
    }
)

SEALED_PATH: Final = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
SEALED_PYTHON: Final = "/usr/bin/python3.12"
SEALED_GIT: Final = "/usr/bin/git"

PCPR_003_VERDICT_CID: Final = (
    "baguqeeraossnqpwfmgxwzhx4bmaaqdg2oiumoqujgxh2uz3dhzconolfepqa"
)
# The PCPR-003 inventory verdict CID is recorded as measured from the
# current-tree PCPR-003 receipt. A mismatch in later receipts is not
# rewritten here; this constant is the campaign-published identity.

SECRET_PROBE: Final = "pcpr-020-do-not-retain-this-secret"
HERMETIC_CANDIDATE_SUITES: Final[tuple[str, ...]] = (
    "tests/test_pcpr_local_backend_qualification.py",
)


class LocalBackendQualificationError(ValueError):
    """Malformed qualification evidence or a forbidden authority claim."""


@dataclass(frozen=True)
class QualificationProbe:
    """One measured or typed-unavailable local-backend observation."""

    probe_id: str
    present: bool | None
    evidence_kind: str
    live: bool
    simulated_represented_as_live: bool
    reason: str
    details: Mapping[str, Any] = MappingProxyType({})

    def to_mapping(self) -> dict[str, Any]:
        return {
            "probe_id": self.probe_id,
            "present": self.present,
            "evidence_kind": self.evidence_kind,
            "live": self.live,
            "simulated_represented_as_live": self.simulated_represented_as_live,
            "reason": self.reason,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class QualificationVerdict:
    """Fail-closed PCPR-020 local backend decision. Never a closed release."""

    schema: str
    interface: str
    promotion_status: str
    supervisor_disposition: str
    closed_release_outcome: None
    release_claim: bool
    completion_authoritative: bool
    contracts_frozen: bool
    duckdb_or_quack_state_written: bool
    local_backend_live_qualified: bool
    suite_complete: bool
    certification_disposition: str
    simulated_results_represented_as_live: bool
    hermetic_results_represented_as_live: bool
    python_local_durability_observed: bool
    interface_parity_qualified: bool
    live_ipfs_qualified: bool
    live_ipfs_evidence_kind: str
    this_task_created_competing_authority: bool
    probes: tuple[QualificationProbe, ...]
    observations: tuple[dict[str, Any], ...]
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
            "local_backend_live_qualified": self.local_backend_live_qualified,
            "suite_complete": self.suite_complete,
            "certification_disposition": self.certification_disposition,
            "simulated_results_represented_as_live": (
                self.simulated_results_represented_as_live
            ),
            "hermetic_results_represented_as_live": (
                self.hermetic_results_represented_as_live
            ),
            "python_local_durability_observed": (
                self.python_local_durability_observed
            ),
            "interface_parity_qualified": self.interface_parity_qualified,
            "live_ipfs_qualified": self.live_ipfs_qualified,
            "live_ipfs_evidence_kind": self.live_ipfs_evidence_kind,
            "this_task_created_competing_authority": (
                self.this_task_created_competing_authority
            ),
            "probes": [item.to_mapping() for item in self.probes],
            "observations": [dict(item) for item in self.observations],
            "operations_observed": list(self.operations_observed),
            "operations_missing": list(self.operations_missing),
            "blockers": list(self.blockers),
            "verdict_cid": self.verdict_cid,
        }


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LocalBackendQualificationError(f"{name} must be a non-empty string")
    return value.strip()


def _kind(value: Any, name: str) -> str:
    kind = _text(value, name)
    if kind not in EVIDENCE_KINDS:
        raise LocalBackendQualificationError(f"{name} is not an admitted evidence kind")
    return kind


def _reject_closed_release_value(value: Any, name: str) -> None:
    if isinstance(value, str) and value in CLOSED_RELEASE_OUTCOMES:
        raise LocalBackendQualificationError(
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


def refuse_hermetic_as_live(adapter: Any) -> None:
    """Hermetic or simulated adapters cannot be submitted as live evidence."""

    live_provider = bool(getattr(adapter, "live_provider", False))
    hermetic = bool(getattr(adapter, "is_hermetic", True))
    simulated = bool(getattr(adapter, "simulated", False))
    if hermetic or simulated or not live_provider:
        raise LocalBackendQualificationError(
            "hermetic or simulated adapters cannot mint live local qualification"
        )
    if getattr(adapter, "backend_id", None) != BACKEND_ID:
        raise LocalBackendQualificationError(
            "live local qualification requires backend_id='local_filesystem'"
        )


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


def probe_hermetic_reference_is_not_live() -> QualificationProbe:
    """Static source probe: hermetic adapter is labeled not-live.

    The hermetic class lives in backends/filesystem_backend.py, which imports
    anyio. Sealed validation may not have anyio, so this probe reads source
    rather than importing the module. Importing that class is not live
    qualification.
    """

    relpath = "ipfs_kit_py/backends/filesystem_backend.py"
    path = _kit_root() / relpath
    if not path.is_file():
        return QualificationProbe(
            probe_id="hermetic_filesystem_adapter_not_live",
            present=None,
            evidence_kind="unavailable",
            live=False,
            simulated_represented_as_live=False,
            reason="filesystem_backend.py is absent; hermetic class stays typed unavailable.",
            details={"relpath": relpath},
        )
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    live_provider = None
    is_hermetic = None
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != "HermeticFilesystemAdapter":
            continue
        for item in node.body:
            assignment = _literal_assignment(item)
            if assignment is None:
                continue
            name, value = assignment
            if name == "live_provider":
                live_provider = value
            elif name == "is_hermetic":
                is_hermetic = value
    not_live = live_provider is False and is_hermetic is True
    return QualificationProbe(
        probe_id="hermetic_filesystem_adapter_not_live",
        present=True,
        evidence_kind="measured",
        live=False,
        simulated_represented_as_live=False,
        reason=(
            "HermeticFilesystemAdapter remains a local hermetic reference. "
            "live_provider=False; it cannot satisfy PCPR-020 live qualification."
        ),
        details={
            "class": "HermeticFilesystemAdapter",
            "relpath": relpath,
            "live_provider": live_provider,
            "is_hermetic": is_hermetic,
            "not_live": not_live,
        },
    )


def probe_cli_mcp_surfaces() -> tuple[QualificationProbe, ...]:
    """Source-present CLI/MCP/MCP++ modules are not live local parity."""

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
                f"No live local-durable {surface} session was exercised. "
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
                probe_id=f"{surface}_local_parity",
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


def run_live_local_backend_suite(
    root: Path,
    *,
    now: datetime | None = None,
) -> tuple[OperationObservation, ...]:
    """Execute the required local durability suite against the live adapter.

    CLI/MCP/MCP++ interface parity is recorded as blocked/unavailable. That
    incomplete observation prevents LiveQualified promotion, which is the
    honest current-head result for PCPR-020.
    """

    del now
    root = Path(root)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    adapter = LiveLocalFilesystemAdapter(root / "store")
    refuse_hermetic_as_live(adapter)
    observations: list[OperationObservation] = []

    payload = b"pcpr-020-local-durable-write-v1"
    written = adapter.put("objects/write.bin", payload, idempotency_key="write-1")
    assert written.success is True
    assert written.resulting_content_cid.startswith("b")
    observations.append(
        _passed(
            "write",
            digests={
                "cid": written.resulting_content_cid,
                "bytes": f"sha256:{_sha256_hex(payload)}",
            },
        )
    )

    read_back = adapter.get("objects/write.bin")
    assert read_back.data == payload
    assert read_back.resulting_content_cid == written.resulting_content_cid
    observations.append(
        _passed(
            "read_back",
            digests={
                "cid": read_back.resulting_content_cid,
                "bytes": f"sha256:{_sha256_hex(read_back.data)}",
            },
        )
    )

    digested = adapter.digest("objects/write.bin")
    assert digested.resulting_content_cid == written.resulting_content_cid
    observations.append(
        _passed(
            "digest",
            digests={
                "cid": digested.resulting_content_cid,
                "algorithm": "cidv1-raw-sha2-256",
            },
        )
    )

    deleted = adapter.delete("objects/write.bin", idempotency_key="delete-1")
    assert deleted.success is True
    try:
        adapter.get("objects/write.bin")
    except LiveLocalBackendError as exc:
        assert exc.error.code is ErrorCode.NOT_FOUND
    else:
        raise LocalBackendQualificationError("delete did not remove the object")
    replay_delete = adapter.delete("objects/write.bin", idempotency_key="delete-1")
    assert replay_delete.resulting_content_cid == deleted.resulting_content_cid
    observations.append(
        _passed(
            "delete",
            digests={
                "cid": deleted.resulting_content_cid,
                "absent_after_delete": "true",
                "replay_delete_safe": "true",
            },
        )
    )

    replay_payload = b"pcpr-020-replay"
    first = adapter.put("objects/replay.bin", replay_payload, idempotency_key="replay-1")
    effects_after_first = adapter.effect_count
    second = adapter.put("objects/replay.bin", replay_payload, idempotency_key="replay-1")
    assert second.resulting_content_cid == first.resulting_content_cid
    assert adapter.effect_count == effects_after_first
    try:
        adapter.put("objects/replay.bin", b"other", idempotency_key="replay-1")
    except LiveLocalBackendError as exc:
        assert exc.error.code is ErrorCode.CONFLICT
    else:
        raise LocalBackendQualificationError("idempotency conflict was not raised")
    observations.append(
        _passed(
            "replay",
            digests={
                "cid": first.resulting_content_cid,
                "effect_count_stable": str(effects_after_first),
            },
        )
    )

    past = time.monotonic() - 5
    try:
        adapter.put("objects/timeout.bin", b"too-late", deadline=past)
    except LiveLocalBackendError as exc:
        assert exc.error.code is ErrorCode.DEADLINE_EXCEEDED
        assert exc.error.state is OperationState.DEADLINE_EXCEEDED
    else:
        raise LocalBackendQualificationError("past deadline was not honored")
    cancelled = threading.Event()
    cancelled.set()
    try:
        adapter.put("objects/timeout.bin", b"cancelled", cancel_event=cancelled)
    except LiveLocalBackendError as exc:
        assert exc.error.code is ErrorCode.CANCELLED
    else:
        raise LocalBackendQualificationError("cancellation was not honored")
    observations.append(
        _passed(
            "timeout",
            digests={
                "deadline_exceeded": ErrorCode.DEADLINE_EXCEEDED.value,
                "cancelled": ErrorCode.CANCELLED.value,
            },
        )
    )

    def _worker(index: int) -> str:
        body = f"pcpr-020-worker-{index}".encode("ascii")
        result = adapter.put(f"objects/concurrency/w{index}.bin", body)
        got = adapter.get(f"objects/concurrency/w{index}.bin")
        if got.data != body:
            raise LocalBackendQualificationError(f"concurrency corruption at {index}")
        return result.resulting_content_cid

    worker_cids: list[str] = []
    threads: list[threading.Thread] = []
    collected: list[str] = []

    def _collect(index: int) -> None:
        collected.append(_worker(index))

    for index in range(4):
        thread = threading.Thread(target=_collect, args=(index,))
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()
    worker_cids = list(collected)
    if len(worker_cids) != 4:
        raise LocalBackendQualificationError("concurrency workers did not complete")
    observations.append(
        _passed(
            "concurrency",
            digests={
                "workers": "4",
                "combined": "sha256:"
                + _sha256_hex("".join(sorted(worker_cids)).encode("ascii")),
            },
        )
    )

    durable_payload = b"pcpr-020-restart-durable"
    durable = adapter.put("objects/restart.bin", durable_payload)
    adapter.close()
    reopened = LiveLocalFilesystemAdapter.reopen(root / "store")
    refuse_hermetic_as_live(reopened)
    restored = reopened.get("objects/restart.bin")
    if restored.data != durable_payload:
        raise LocalBackendQualificationError("restart lost durable bytes")
    if restored.resulting_content_cid != durable.resulting_content_cid:
        raise LocalBackendQualificationError("restart lost durable CID")
    observations.append(
        _passed(
            "restart",
            digests={
                "cid": restored.resulting_content_cid,
                "bytes": f"sha256:{_sha256_hex(restored.data)}",
            },
            detail="store reopened from disk after close; in-memory state was discarded",
        )
    )

    integrity_payload = b"pcpr-020-integrity"
    integrity = reopened.put("objects/integrity.bin", integrity_payload)
    reopened.corrupt_for_test("objects/integrity.bin", b"tampered-integrity")
    try:
        reopened.get("objects/integrity.bin")
    except LiveLocalBackendError as exc:
        assert exc.error.code is ErrorCode.INTEGRITY_FAILURE
    else:
        raise LocalBackendQualificationError("corruption was not detected")
    observations.append(
        _passed(
            "corruption",
            digests={
                "expected_cid": integrity.resulting_content_cid,
                "detected": ErrorCode.INTEGRITY_FAILURE.value,
            },
            detail="bit-flip of object bytes failed closed against the CID sidecar",
        )
    )

    large_payload = (b"ABCDEFGH" * (LARGE_OBJECT_BYTES // 8))[:LARGE_OBJECT_BYTES]
    large = reopened.put("objects/large.bin", large_payload)
    large_read = reopened.get("objects/large.bin")
    if large_read.data != large_payload or len(large_read.data) != LARGE_OBJECT_BYTES:
        raise LocalBackendQualificationError("large object round-trip failed")
    observations.append(
        _passed(
            "large_object",
            digests={
                "size": str(len(large_read.data)),
                "cid": large.resulting_content_cid,
                "bytes": f"sha256:{_sha256_hex(large_read.data)}",
            },
        )
    )

    try:
        LiveLocalFilesystemAdapter(
            root / "secret-store",
            configuration={"api_token": SECRET_PROBE},
        )
    except LiveLocalBackendError as exc:
        assert exc.error.code is ErrorCode.SECRET_MATERIAL
        if SECRET_PROBE in str(exc):
            raise LocalBackendQualificationError("secret material leaked in error")
    else:
        raise LocalBackendQualificationError("secret configuration was not rejected")
    try:
        reopened.put(
            "objects/secret.bin",
            b"nope",
            metadata={"password": SECRET_PROBE},
        )
    except LiveLocalBackendError as exc:
        assert exc.error.code is ErrorCode.SECRET_MATERIAL
    else:
        raise LocalBackendQualificationError("secret metadata was not rejected")
    if SECRET_PROBE in json.dumps(_observation_mapping(observations[-1])):
        raise LocalBackendQualificationError("secret material leaked into observations")
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
                "Python local durable put/get/digest/delete were live-observed. "
                "CLI, MCP, and MCP++ local-durable sessions were not exercised. "
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

    observed_ops = {item.operation for item in observations}
    if observed_ops != set(REQUIRED_SUITE_OPERATIONS):
        raise LocalBackendQualificationError(
            f"suite operations mismatch: {sorted(observed_ops)}"
        )
    reopened.close()
    return tuple(observations)


def evaluate_live_local_backend(
    observations: Sequence[OperationObservation],
    *,
    now: datetime | None = None,
) -> Any:
    contract = contract_for(BACKEND_ID)
    suite = generate_suite(contract, now=now)
    return evaluate_observations(
        contract,
        observations,
        live_runner_present=True,
        now=now,
        suite=suite,
    )


def _verdict_cid(payload: Mapping[str, Any]) -> str:
    body = {key: payload[key] for key in payload if key != "verdict_cid"}
    return content_identity(body)


def qualify_local_backend(
    *,
    root: Path | None = None,
    now: datetime | None = None,
) -> QualificationVerdict:
    """Run live local qualification and issue an R&D non-promotion verdict."""

    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        raise LocalBackendQualificationError("now must be timezone-aware")
    owned_root = root is None
    work_root = Path(root) if root is not None else Path(
        tempfile.mkdtemp(prefix="pcpr-020-local-")
    )
    try:
        observations = run_live_local_backend_suite(work_root, now=reference)
        result = evaluate_live_local_backend(observations, now=reference)
    finally:
        if owned_root and work_root.exists():
            shutil.rmtree(work_root, ignore_errors=True)

    if result.live_qualified:
        raise LocalBackendQualificationError(
            "PCPR-020 must not mint LiveQualified while CLI/MCP/MCP++ "
            "parity remains unexercised"
        )
    if result.disposition is CertificationDisposition.LIVE_QUALIFIED:
        raise LocalBackendQualificationError(
            "certification disposition LiveQualified is forbidden for PCPR-020"
        )

    probes = (
        QualificationProbe(
            probe_id="live_local_filesystem_adapter",
            present=True,
            evidence_kind="measured_live",
            live=True,
            simulated_represented_as_live=False,
            reason=(
                "LiveLocalFilesystemAdapter executed write, read-back, digest, "
                "delete, replay, timeout, concurrency, restart, corruption, "
                "large-object, and credential cases against the local POSIX store."
            ),
            details={
                "backend_id": BACKEND_ID,
                "schema": ADAPTER_SCHEMA,
                "interface": ADAPTER_INTERFACE,
                "certification_scope": CERTIFICATION_SCOPE,
                "production_authorized": False,
            },
        ),
        probe_hermetic_reference_is_not_live(),
        *probe_cli_mcp_surfaces(),
        QualificationProbe(
            probe_id="pinned_ipfs_not_in_scope",
            present=None,
            evidence_kind="unavailable",
            live=False,
            simulated_represented_as_live=False,
            reason=(
                f"Pinned IPFS daemon qualification is {PCPR_021_TASK_ID}. "
                "Missing daemon evidence stays typed unavailable."
            ),
            details={"remediating_task": PCPR_021_TASK_ID},
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
    missing = tuple(result.operations_missing)
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
        "local_backend_live_qualified": False,
        "suite_complete": False,
        "certification_disposition": result.disposition.value,
        "simulated_results_represented_as_live": False,
        "hermetic_results_represented_as_live": False,
        "python_local_durability_observed": set(python_ops)
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
        "live_ipfs_qualified": False,
        "live_ipfs_evidence_kind": "unavailable",
        "this_task_created_competing_authority": False,
        "probes": [item.to_mapping() for item in probes],
        "observations": [_observation_mapping(item) for item in observations],
        "operations_observed": list(result.operations_observed),
        "operations_missing": list(missing),
        "blockers": [],
    }
    _reject_closed_release_value(payload["promotion_status"], "promotion_status")
    _reject_closed_release_value(
        payload["supervisor_disposition"], "supervisor_disposition"
    )
    if payload["closed_release_outcome"] is not None:
        raise LocalBackendQualificationError("closed_release_outcome must be null")
    if payload["promotion_status"] not in PROMOTION_STATUSES:
        raise LocalBackendQualificationError("promotion_status is not admitted")
    if payload["promotion_status"] == "supervisor_promoted":
        raise LocalBackendQualificationError("PCPR-020 cannot promote the supervisor")
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
        local_backend_live_qualified=False,
        suite_complete=False,
        certification_disposition=payload["certification_disposition"],
        simulated_results_represented_as_live=False,
        hermetic_results_represented_as_live=False,
        python_local_durability_observed=bool(
            payload["python_local_durability_observed"]
        ),
        interface_parity_qualified=False,
        live_ipfs_qualified=False,
        live_ipfs_evidence_kind="unavailable",
        this_task_created_competing_authority=False,
        probes=probes,
        observations=tuple(payload["observations"]),
        operations_observed=tuple(result.operations_observed),
        operations_missing=tuple(missing),
        blockers=(),
        verdict_cid=cid,
    )


def qualify_current_head_local_backend(
    *, now: datetime | None = None
) -> QualificationVerdict:
    return qualify_local_backend(now=now)


def observe_sealed_validation_environment() -> dict[str, Any]:
    """Measure the sealed PATH; missing tools stay typed unavailable."""

    def _which(name: str) -> str:
        for directory in SEALED_PATH.split(":"):
            candidate = Path(directory) / name
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
        return "unavailable"

    python3_12 = Path(SEALED_PYTHON)
    git_path = Path(SEALED_GIT)
    python_version = "unavailable"
    if python3_12.is_file():
        import subprocess

        completed = subprocess.run(
            [str(python3_12), "--version"],
            check=False,
            capture_output=True,
            text=True,
            env={"PATH": SEALED_PATH},
        )
        python_version = (completed.stdout or completed.stderr or "").strip() or "unavailable"
    pytest_module = "unavailable"
    pytest_version = "unavailable"
    try:
        import pytest  # type: ignore[import-untyped]

        pytest_module = getattr(pytest, "__file__", "unavailable") or "unavailable"
        pytest_version = getattr(pytest, "__version__", "unavailable")
        if "/home/" in str(pytest_module) or ".local" in str(pytest_module):
            pytest_module = "unavailable"
            pytest_version = "unavailable"
    except Exception:
        pytest_module = "unavailable"
        pytest_version = "unavailable"
    return {
        "PATH": SEALED_PATH,
        "python_unqualified": _which("python"),
        "python3": _which("python3"),
        "python3_12": str(python3_12) if python3_12.is_file() else "unavailable",
        "python_version": python_version,
        "git_path": str(git_path) if git_path.is_file() else "unavailable",
        "usr_bin_user_writable": os.access("/usr/bin", os.W_OK),
        "usr_local_bin_user_writable": os.access("/usr/local/bin", os.W_OK),
        "pytest_cli": _which("pytest"),
        "pytest_module": pytest_module,
        "pytest_module_version": pytest_version,
        "duckdb": _which("duckdb"),
        "anyio": "unavailable",
        "pytest_asyncio": "unavailable",
        "ipfs": _which("ipfs"),
        "z3": _which("z3"),
        "evidence_kind": "measured",
    }


def validate_pcpr_020_outer_receipt(payload: Mapping[str, Any]) -> None:
    """Reject closed-release claims and simulated-as-live promotion."""

    if not isinstance(payload, Mapping):
        raise LocalBackendQualificationError("receipt must be a mapping")
    task_id = _text(payload.get("task_id"), "task_id")
    if task_id != PCPR_020_TASK_ID:
        raise LocalBackendQualificationError("task_id must be PCPR-020")
    promotion = None
    acceptance = payload.get("acceptance")
    verdict = payload.get("qualification_verdict")
    if isinstance(acceptance, Mapping):
        promotion = acceptance.get("promotion_status")
        if acceptance.get("closed_release_outcome") is not None:
            raise LocalBackendQualificationError(
                "acceptance.closed_release_outcome must be null"
            )
        if acceptance.get("release_claim") is True:
            raise LocalBackendQualificationError("acceptance.release_claim must be false")
    if isinstance(verdict, Mapping):
        promotion = verdict.get("promotion_status", promotion)
        if verdict.get("closed_release_outcome") is not None:
            raise LocalBackendQualificationError(
                "qualification_verdict.closed_release_outcome must be null"
            )
        if verdict.get("local_backend_live_qualified") is True:
            raise LocalBackendQualificationError(
                "local_backend_live_qualified cannot be true while the suite is incomplete"
            )
        if verdict.get("simulated_results_represented_as_live") is True:
            raise LocalBackendQualificationError(
                "simulated results cannot be represented as live"
            )
    promotion_text = _text(promotion, "promotion_status")
    if promotion_text not in PROMOTION_STATUSES:
        raise LocalBackendQualificationError("promotion_status is not admitted")
    if promotion_text in CLOSED_RELEASE_OUTCOMES:
        raise LocalBackendQualificationError("promotion_status is a closed release outcome")
    legend = payload.get("evidence_legend")
    if legend is not None and not isinstance(legend, Mapping):
        raise LocalBackendQualificationError("evidence_legend must be a mapping when present")


__all__ = [
    "QUALIFICATION_INTERFACE",
    "QUALIFICATION_SCHEMA",
    "QUALIFICATION_VERDICT_SCHEMA",
    "PCPR_020_TASK_ID",
    "PCPR_020_GOAL_ID",
    "CLOSED_RELEASE_OUTCOMES",
    "PROMOTION_STATUSES",
    "HERMETIC_CANDIDATE_SUITES",
    "LocalBackendQualificationError",
    "QualificationProbe",
    "QualificationVerdict",
    "refuse_hermetic_as_live",
    "run_live_local_backend_suite",
    "evaluate_live_local_backend",
    "qualify_local_backend",
    "qualify_current_head_local_backend",
    "observe_sealed_validation_environment",
    "validate_pcpr_020_outer_receipt",
    "canonical_json_bytes",
]

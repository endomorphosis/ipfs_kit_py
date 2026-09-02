"""Fail-closed PCPR-023 VFS/WAL/current-root recovery qualification.

PCPR-023 qualifies hermetic VFS plus WAL recovery, current-root CAS, ARC
coherence, crash recovery, stale-root rejection, corruption, tombstone,
invalidation, concurrent writers, restart, and mount lifecycle. Linux FUSE,
Windows WinFsp, and container FUSE are live only where a real driver exists.
Missing environments stay typed unavailable. Hermetic and simulated results
cannot mint live qualification. CLI, MCP, and MCP++ parity remain typed
unavailable until PCPR-026. Proof-seal witness and key protection remain
typed unavailable until PCPR-024.

This module is not release authority: it does not write DuckDB or Quack
state and never emits a closed PCPR release outcome.
"""

from __future__ import annotations

import os
import platform
import shutil
import sys
import tempfile
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

from ipfs_kit_py.assurance.backend_certification import (
    CertificationDisposition,
)
from ipfs_kit_py.assurance.local_backend_qualification import (
    CLOSED_RELEASE_OUTCOMES,
    EVIDENCE_KINDS,
    PROMOTION_STATUSES,
    SEALED_PATH,
    QualificationProbe,
    observe_sealed_validation_environment,
)
from ipfs_kit_py.assurance.vfs_wal_recovery import (
    BACKEND_ID,
    CERTIFICATION_SCOPE,
    GENESIS_PARENT,
    INTERFACE as ADAPTER_INTERFACE,
    LIVE_SUPPORT_CLAIM,
    SCHEMA as ADAPTER_SCHEMA,
    SUPPORT_CLASS,
    DurableCurrentRootCAS,
    HermeticVfsWalRecoveryAdapter,
    VfsWalRecoveryError,
    WALTransactionCrash,
    content_cid,
)
from ipfs_kit_py.core.operation_contracts import (
    ErrorCode,
    content_identity,
)
from ipfs_kit_py.kernel_vfs.linux import LinuxMountConfig, LinuxMountLifecycle
from ipfs_kit_py.kernel_vfs.platform import run_linux_doctor
from ipfs_kit_py.kernel_vfs.winfsp_loader import run_windows_doctor


QUALIFICATION_INTERFACE: Final = "VfsWalQualification@1"
QUALIFICATION_SCHEMA: Final = "ipfs_kit_py/assurance/vfs-wal-qualification@1"
QUALIFICATION_VERDICT_SCHEMA: Final = (
    "ipfs_kit_py/assurance/vfs-wal-qualification-verdict@1"
)

PCPR_023_TASK_ID: Final = "PCPR-023"
PCPR_023_GOAL_ID: Final = "PCPR-G300"
PCPR_022_TASK_ID: Final = "PCPR-022"
PCPR_024_TASK_ID: Final = "PCPR-024"
PCPR_026_TASK_ID: Final = "PCPR-026"
PCPR_027_TASK_ID: Final = "PCPR-027"
PCPR_PROGRAM_ID: Final = "proof-carrying-platform-qualification-and-release-v1"
PCPR_BOARD_NAMESPACE: Final = "proof-carrying-platform-qualification-and-release-v1"

SECRET_PROBE: Final = "pcpr-023-do-not-retain-this-secret"
HERMETIC_CANDIDATE_SUITES: Final[tuple[str, ...]] = (
    "tests/test_pcpr_vfs_wal_qualification.py",
)

REQUIRED_RECOVERY_OPERATIONS: Final[tuple[str, ...]] = (
    "restart",
    "concurrent_writers",
    "stale_parent",
    "corruption",
    "tombstone",
    "invalidation",
    "mount_lifecycle",
    "wal_recovery",
    "current_root_cas",
    "arc_coherence",
    "crash_recovery",
    "stale_root_rejection",
)

LIVE_DRIVER_OPERATIONS: Final[tuple[str, ...]] = (
    "linux_fuse",
    "windows_winfsp",
    "container_fuse",
)


class VfsWalQualificationError(ValueError):
    """Malformed qualification evidence or a forbidden authority claim."""


@dataclass(frozen=True)
class QualificationVerdict:
    """Fail-closed PCPR-023 VFS/WAL decision. Never a closed release."""

    schema: str
    interface: str
    promotion_status: str
    supervisor_disposition: str
    closed_release_outcome: None
    release_claim: bool
    completion_authoritative: bool
    contracts_frozen: bool
    duckdb_or_quack_state_written: bool
    vfs_live_qualified: bool
    suite_complete: bool
    certification_disposition: str
    support_class: str
    live_support_claim: bool
    simulated_results_represented_as_live: bool
    hermetic_results_represented_as_live: bool
    hermetic_vfs_observed: bool
    linux_fuse_live_qualified: bool
    windows_winfsp_live_qualified: bool
    container_fuse_live_qualified: bool
    interface_parity_qualified: bool
    live_fuse_evidence_kind: str
    this_task_created_competing_authority: bool
    probes: tuple[QualificationProbe, ...]
    observations: tuple[dict[str, Any], ...]
    hermetic_operations: tuple[dict[str, Any], ...]
    live_driver_operations: tuple[dict[str, Any], ...]
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
            "vfs_live_qualified": self.vfs_live_qualified,
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
            "hermetic_vfs_observed": self.hermetic_vfs_observed,
            "linux_fuse_live_qualified": self.linux_fuse_live_qualified,
            "windows_winfsp_live_qualified": self.windows_winfsp_live_qualified,
            "container_fuse_live_qualified": self.container_fuse_live_qualified,
            "interface_parity_qualified": self.interface_parity_qualified,
            "live_fuse_evidence_kind": self.live_fuse_evidence_kind,
            "this_task_created_competing_authority": (
                self.this_task_created_competing_authority
            ),
            "probes": [item.to_mapping() for item in self.probes],
            "observations": [dict(item) for item in self.observations],
            "hermetic_operations": [dict(item) for item in self.hermetic_operations],
            "live_driver_operations": [
                dict(item) for item in self.live_driver_operations
            ],
            "operations_observed": list(self.operations_observed),
            "operations_missing": list(self.operations_missing),
            "blockers": list(self.blockers),
            "verdict_cid": self.verdict_cid,
        }


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise VfsWalQualificationError(f"{name} must be a non-empty string")
    return value.strip()


def _kind(value: Any, name: str) -> str:
    kind = _text(value, name)
    if kind not in EVIDENCE_KINDS:
        raise VfsWalQualificationError(f"{name} is not an admitted evidence kind")
    return kind


def _reject_closed_release_value(value: Any, name: str) -> None:
    if isinstance(value, str) and value in CLOSED_RELEASE_OUTCOMES:
        raise VfsWalQualificationError(
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


def _unobserved(operation: str, reason: str) -> dict[str, Any]:
    return {
        "operation": operation,
        "status": "unobserved",
        "environment": "live",
        "source": "unavailable",
        "signature_valid": False,
        "freshness": "missing",
        "digests": {"reason": reason},
        "limitations": ["driver_unavailable"],
        "detail": reason,
        "evidence_kind": "unavailable",
        "live": False,
        "simulated_represented_as_live": False,
        "hermetic_represented_as_live": False,
    }


def _driver_operation(
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
        "environment": "live" if live else "sealed",
        "source": "live_observed" if live else "unavailable",
        "evidence_kind": evidence_kind,
        "live": live,
        "simulated_represented_as_live": False,
        "hermetic_represented_as_live": False,
        "reason": reason,
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


def refuse_simulated_as_live(adapter: Any) -> None:
    """Hermetic, simulated, or live-claiming adapters cannot mint live FUSE evidence."""

    live_provider = bool(getattr(adapter, "live_provider", False))
    hermetic = bool(getattr(adapter, "is_hermetic", True))
    simulated = bool(getattr(adapter, "simulated", False))
    live_claim = bool(getattr(adapter, "live_support_claim", False))
    if hermetic or simulated or not live_provider or live_claim:
        raise VfsWalQualificationError(
            "hermetic or simulated adapters cannot mint live VFS qualification"
        )
    if getattr(adapter, "backend_id", None) != BACKEND_ID:
        raise VfsWalQualificationError(
            "live VFS qualification requires backend_id='vfs_wal_current_root'"
        )


def refuse_hermetic_as_live(adapter: Any) -> None:
    """Explicit alias: hermetic recovery cannot be submitted as live FUSE."""

    refuse_simulated_as_live(adapter)


def sealed_which(name: str) -> str:
    """Resolve an executable on the sealed validation PATH only."""

    for directory in SEALED_PATH.split(":"):
        candidate = Path(directory) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return "unavailable"


def probe_linux_fuse() -> QualificationProbe:
    report = run_linux_doctor(path_env=SEALED_PATH)
    ready = bool(report.get("native_capability_ready"))
    absences = report.get("checks", {}).get("actionable_absence", {}).get("items") or []
    absence_text = "; ".join(
        str(item.get("message") or item.get("check") or "absence")
        for item in absences
        if isinstance(item, Mapping)
    )
    return QualificationProbe(
        probe_id="linux_fuse_doctor",
        present=ready,
        evidence_kind="measured" if ready else "unavailable",
        live=False,
        simulated_represented_as_live=False,
        reason=(
            "Linux FUSE doctor reports native_capability_ready. Live kernel "
            "mount was not started by this qualifier."
            if ready
            else (
                "Linux FUSE doctor reports capability_unavailable. "
                + (absence_text or "Missing native FUSE capability")
                + " stays typed unavailable and is not recorded as zero or "
                "passing. Hermetic VFS is not live FUSE."
            )
        ),
        details={
            "native_capability_ready": ready,
            "support_claim": report.get("support_claim"),
            "mounted": False,
            "absences": absences,
            "PATH": SEALED_PATH,
            "dev_fuse": report.get("checks", {}).get("dev_fuse", {}),
            "fusermount_helper": report.get("checks", {}).get("fusermount_helper", {}),
            "libfuse2_abi": report.get("checks", {}).get("libfuse2_abi", {}),
            "python_binding": report.get("checks", {}).get("python_binding", {}),
        },
    )


def probe_windows_winfsp() -> QualificationProbe:
    if platform.system().casefold() != "windows":
        return QualificationProbe(
            probe_id="windows_winfsp_doctor",
            present=False,
            evidence_kind="unavailable",
            live=False,
            simulated_represented_as_live=False,
            reason=(
                "Host OS is not Windows. WinFsp live support is typed "
                "unavailable and is not recorded as zero or passing."
            ),
            details={
                "os": platform.system(),
                "native_capability_ready": False,
                "mounted": False,
            },
        )
    report = run_windows_doctor()
    ready = bool(report.get("native_capability_ready"))
    return QualificationProbe(
        probe_id="windows_winfsp_doctor",
        present=ready,
        evidence_kind="measured" if ready else "unavailable",
        live=False,
        simulated_represented_as_live=False,
        reason=(
            "Windows WinFsp doctor reports native_capability_ready. Live "
            "mount was not started by this qualifier."
            if ready
            else (
                "Windows WinFsp doctor reports capability_unavailable. "
                "Missing driver stays typed unavailable."
            )
        ),
        details={
            "native_capability_ready": ready,
            "support_claim": report.get("support_claim"),
            "mounted": False,
        },
    )


def probe_container_fuse() -> QualificationProbe:
    docker = sealed_which("docker")
    podman = sealed_which("podman")
    present = docker != "unavailable" or podman != "unavailable"
    dev_fuse = Path("/dev/fuse").exists()
    live_ready = present and dev_fuse
    return QualificationProbe(
        probe_id="container_fuse",
        present=live_ready,
        evidence_kind="measured" if live_ready else "unavailable",
        live=False,
        simulated_represented_as_live=False,
        reason=(
            "A container runtime and /dev/fuse are present. Live container "
            "FUSE was not started by this qualifier."
            if live_ready
            else (
                "Sealed PATH has no usable docker/podman runtime and/or "
                "/dev/fuse is absent. Container FUSE stays typed unavailable "
                "and is not recorded as zero or passing."
            )
        ),
        details={
            "docker": docker,
            "podman": podman,
            "dev_fuse": "/dev/fuse" if dev_fuse else "unavailable",
            "PATH": SEALED_PATH,
            "live_container_started": False,
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
                f"No live VFS/WAL {surface} session was exercised. "
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
                probe_id=f"{surface}_vfs_parity",
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


def _corrupt_pointer(root: Path) -> None:
    pointer = root / "current-root.json"
    pointer.write_bytes(b'{"schema":"corrupt","generation":1}')


def run_hermetic_vfs_wal_suite(root: Path) -> tuple[dict[str, Any], ...]:
    """Exercise mandatory hermetic VFS/WAL/current-root recovery cases.

    Results are measured_hermetic. They cannot mint live FUSE qualification
    or a closed PCPR release.
    """

    root = Path(root)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    observations: list[dict[str, Any]] = []

    adapter = HermeticVfsWalRecoveryAdapter(root / "store")
    try:
        first = adapter.compare_and_swap_current_root(GENESIS_PARENT, b"pcpr-023-root-v1")
        if not first.swapped or first.pointer.generation != 1:
            raise VfsWalQualificationError("genesis current-root CAS failed")
        observations.append(
            _hermetic_passed(
                "current_root_cas",
                digests={
                    "cid": first.object_cid,
                    "generation": str(first.pointer.generation),
                    "bytes": f"sha256:{content_cid(b'pcpr-023-root-v1')}",
                },
                detail="genesis current-root CAS published generation 1",
            )
        )

        stale_errors: list[str] = []

        def _stale() -> None:
            try:
                adapter.compare_and_swap_current_root(GENESIS_PARENT, b"stale-loser")
            except VfsWalRecoveryError as exc:
                stale_errors.append(exc.error.code.value)

        stale_thread = threading.Thread(target=_stale)
        stale_thread.start()
        stale_thread.join(timeout=5)
        if ErrorCode.PRECONDITION_FAILED.value not in stale_errors:
            try:
                adapter.compare_and_swap_current_root(GENESIS_PARENT, b"stale-direct")
            except VfsWalRecoveryError as exc:
                stale_errors.append(exc.error.code.value)
            else:
                raise VfsWalQualificationError("stale parent was not rejected")
        observations.append(
            _hermetic_passed(
                "stale_parent",
                digests={"rejected": ErrorCode.PRECONDITION_FAILED.value},
                detail="stale parent CID failed closed",
            )
        )
        observations.append(
            _hermetic_passed(
                "stale_root_rejection",
                digests={"rejected": ErrorCode.PRECONDITION_FAILED.value},
                detail="stale current-root CAS is rejected",
            )
        )

        winners: list[str] = []
        losers: list[str] = []
        parent = adapter.current_root().current_cid
        barrier = threading.Barrier(2)

        def _race(tag: bytes) -> None:
            barrier.wait(timeout=5)
            try:
                result = adapter.compare_and_swap_current_root(parent, tag)
                if result.swapped:
                    winners.append(result.object_cid)
            except VfsWalRecoveryError as exc:
                losers.append(exc.error.code.value)

        first_thread = threading.Thread(target=_race, args=(b"writer-a",))
        second_thread = threading.Thread(target=_race, args=(b"writer-b",))
        first_thread.start()
        second_thread.start()
        first_thread.join(timeout=5)
        second_thread.join(timeout=5)
        if len(winners) != 1 or ErrorCode.PRECONDITION_FAILED.value not in losers:
            raise VfsWalQualificationError(
                f"concurrent writers did not fence: winners={winners} losers={losers}"
            )
        observations.append(
            _hermetic_passed(
                "concurrent_writers",
                digests={
                    "winners": str(len(winners)),
                    "loser": ErrorCode.PRECONDITION_FAILED.value,
                },
                detail="exactly one CAS winner; loser is stale-parent",
            )
        )

        created = adapter.create_object("docs/a.txt", b"wal-payload", effect_id="effect:wal-1")
        if not created.committed:
            raise VfsWalQualificationError("durable mutation did not commit")
        adapter.close()
        reopened = HermeticVfsWalRecoveryAdapter.reopen(root / "store")
        pointer = reopened.current_root()
        if pointer.current_cid != winners[0] and pointer.generation < 1:
            raise VfsWalQualificationError("reopen lost current root")
        recovered_object = reopened.get_current_object(pointer.current_cid)
        if not recovered_object:
            raise VfsWalQualificationError("reopen did not restore current-root bytes")
        wal_stats = reopened.recover_wal()
        observations.append(
            _hermetic_passed(
                "restart",
                digests={
                    "cid": pointer.current_cid,
                    "generation": str(pointer.generation),
                    "mutations_replayed": str(wal_stats.get("mutations_replayed", 0)),
                },
                detail="new adapter instance reconstructed current root from disk",
            )
        )
        observations.append(
            _hermetic_passed(
                "wal_recovery",
                digests={
                    "mutations_replayed": str(wal_stats.get("mutations_replayed", 0)),
                    "mutations_rolled_back": str(wal_stats.get("mutations_rolled_back", 0)),
                },
                detail="WAL recover on reopen is idempotent",
            )
        )

        receipt = reopened.publish_coherence(
            kind="create",
            path="docs/a.txt",
            disposition="committed",
            effect_id="effect:arc-1",
        )
        generation = reopened.active_generation("docs/a.txt")
        if not receipt.published or not generation:
            raise VfsWalQualificationError("ARC coherence did not publish")
        unlink_receipt = reopened.publish_coherence(
            kind="unlink",
            path="docs/a.txt",
            disposition="committed",
            effect_id="effect:arc-2",
        )
        if unlink_receipt.bindings_invalidated < 0:
            raise VfsWalQualificationError("ARC invalidation failed")
        observations.append(
            _hermetic_passed(
                "arc_coherence",
                digests={
                    "generation": generation,
                    "published": str(receipt.published).lower(),
                    "invalidated": str(unlink_receipt.bindings_invalidated),
                },
                detail="committed create advanced generation; unlink invalidated bindings",
            )
        )

        crash_root = root / "crash-cas"
        crash_hits = {"count": 0}

        def _crash(name: str, *_args: object) -> None:
            if name == "after_effect" and crash_hits["count"] == 0:
                crash_hits["count"] += 1
                raise WALTransactionCrash(name)

        crashing = DurableCurrentRootCAS(crash_root, crash_injector=_crash)
        try:
            crashing.compare_and_swap(GENESIS_PARENT, b"crash-payload")
            raise VfsWalQualificationError("crash injector did not fire")
        except WALTransactionCrash:
            crashing.close()
        recovered_cas = DurableCurrentRootCAS.reopen(crash_root)
        stats = recovered_cas.recover()
        after = recovered_cas.current()
        if after.generation != 0:
            raise VfsWalQualificationError(
                "pre-commit crash did not compensate current root"
            )
        observations.append(
            _hermetic_passed(
                "crash_recovery",
                digests={
                    "rolled_back": str(stats.get("rolled_back", 0)),
                    "generation": str(after.generation),
                    "boundary": "after_effect",
                },
                detail="WAL crash after_effect compensated; current root remains genesis",
            )
        )
        recovered_cas.close()

        tombstone_adapter = HermeticVfsWalRecoveryAdapter(root / "tombstone")
        published = tombstone_adapter.compare_and_swap_current_root(
            GENESIS_PARENT, b"to-tombstone"
        )
        tombstoned = tombstone_adapter.tombstone_current_root()
        if not tombstoned.tombstoned:
            raise VfsWalQualificationError("tombstone was not recorded")
        try:
            tombstone_adapter.compare_and_swap_current_root(
                published.object_cid, b"after-tombstone"
            )
        except VfsWalRecoveryError as exc:
            if exc.error.code is not ErrorCode.CONFLICT:
                raise VfsWalQualificationError("tombstone reject used wrong code")
        else:
            raise VfsWalQualificationError("tombstoned root accepted a swap")
        observations.append(
            _hermetic_passed(
                "tombstone",
                digests={"rejected": ErrorCode.CONFLICT.value},
                detail="tombstoned current root rejects subsequent CAS",
            )
        )
        tombstone_adapter.close()

        invalidate_adapter = HermeticVfsWalRecoveryAdapter(root / "invalidate")
        published_inv = invalidate_adapter.compare_and_swap_current_root(
            GENESIS_PARENT, b"to-invalidate"
        )
        invalidated = invalidate_adapter.invalidate_current_root("pcpr-023-invalidation")
        if not invalidated.invalidated:
            raise VfsWalQualificationError("invalidation was not recorded")
        try:
            invalidate_adapter.compare_and_swap_current_root(
                published_inv.object_cid, b"after-invalidation"
            )
        except VfsWalRecoveryError as exc:
            if exc.error.code is not ErrorCode.CONFLICT:
                raise VfsWalQualificationError("invalidation reject used wrong code")
        else:
            raise VfsWalQualificationError("invalidated root accepted a swap")
        observations.append(
            _hermetic_passed(
                "invalidation",
                digests={"rejected": ErrorCode.CONFLICT.value},
                detail="invalidated current root rejects subsequent CAS",
            )
        )
        invalidate_adapter.close()

        corrupt_root = root / "corrupt"
        DurableCurrentRootCAS(corrupt_root)
        _corrupt_pointer(corrupt_root)
        try:
            DurableCurrentRootCAS.reopen(corrupt_root)
        except VfsWalRecoveryError as exc:
            if exc.error.code is not ErrorCode.INTEGRITY_FAILURE:
                raise VfsWalQualificationError("corruption used wrong code")
        else:
            raise VfsWalQualificationError("corrupted pointer was accepted")
        observations.append(
            _hermetic_passed(
                "corruption",
                digests={"detected": ErrorCode.INTEGRITY_FAILURE.value},
                detail="pointer digest mismatch failed closed",
            )
        )

        mount_dir = root / "mount-lifecycle"
        lifecycle = LinuxMountLifecycle(
            LinuxMountConfig(
                mountpoint=mount_dir / "mnt",
                state_directory=mount_dir / "state",
                mount_id="mount:pcpr-023",
                generation_id="wal-gen:pcpr-023",
                readiness_timeout_seconds=10.0,
                heartbeat_interval_seconds=0.05,
                unmount_timeout_seconds=5.0,
                hermetic=True,
                python_executable=sys.executable,
            )
        )
        try:
            readiness = lifecycle.start(wait_ready=True)
            if not readiness.ready or not readiness.recovery_complete:
                raise VfsWalQualificationError("hermetic mount lifecycle was not ready")
            unmount = lifecycle.unmount()
            if not unmount.success:
                raise VfsWalQualificationError("hermetic unmount failed")
            observations.append(
                _hermetic_passed(
                    "mount_lifecycle",
                    digests={
                        "ready": str(readiness.ready).lower(),
                        "recovery_complete": str(readiness.recovery_complete).lower(),
                        "pid": str(readiness.pid),
                        "unmount": unmount.disposition.value,
                    },
                    limitations=("hermetic_child_daemon_not_live_fuse",),
                    detail="hermetic Linux child recovered before ready and unmounted",
                )
            )
        finally:
            try:
                lifecycle.unmount(timeout_seconds=5.0)
            except Exception:
                pass

        try:
            HermeticVfsWalRecoveryAdapter(
                root / "secret", configuration={"api_token": SECRET_PROBE}
            )
        except VfsWalRecoveryError as exc:
            if exc.error.code is not ErrorCode.SECRET_MATERIAL:
                raise VfsWalQualificationError("secret rejection used wrong code")
            if SECRET_PROBE in str(exc):
                raise VfsWalQualificationError("secret material leaked in error")
        else:
            raise VfsWalQualificationError("secret configuration was not rejected")

        mount_receipt = reopened.recover_mount()
        if mount_receipt.disposition is None:
            raise VfsWalQualificationError("mount recovery produced no disposition")
        reopened.close()
    finally:
        try:
            adapter.close()
        except Exception:
            pass

    observed = {item["operation"] for item in observations}
    if observed != set(REQUIRED_RECOVERY_OPERATIONS):
        raise VfsWalQualificationError(
            f"hermetic recovery operations mismatch: {sorted(observed)}"
        )
    return tuple(observations)


def qualify_vfs_wal(
    *,
    root: Path | None = None,
    now: datetime | None = None,
) -> QualificationVerdict:
    """Qualify hermetic VFS/WAL recovery and issue an R&D non-promotion."""

    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        raise VfsWalQualificationError("now must be timezone-aware")
    del reference

    linux_probe = probe_linux_fuse()
    windows_probe = probe_windows_winfsp()
    container_probe = probe_container_fuse()

    owned_root = root is None
    work_root = Path(root) if root is not None else Path(
        tempfile.mkdtemp(prefix="pcpr-023-vfs-")
    )
    hermetic_observed = False
    observations: tuple[dict[str, Any], ...]
    try:
        observations = run_hermetic_vfs_wal_suite(work_root)
        hermetic_observed = True
    except (VfsWalQualificationError, VfsWalRecoveryError, OSError) as exc:
        reason = f"Hermetic VFS/WAL suite failed closed: {exc}."
        observations = tuple(
            _blocked(operation, reason=reason, environment="hermetic")
            for operation in REQUIRED_RECOVERY_OPERATIONS
        )
        hermetic_observed = False
    finally:
        if owned_root and work_root.exists():
            shutil.rmtree(work_root, ignore_errors=True)

    live_reason = (
        "Linux FUSE, Windows WinFsp, and container FUSE were not live-mounted. "
        "Missing native drivers stay typed unavailable. Hermetic VFS is not live."
    )
    live_driver_ops = (
        _driver_operation(
            "linux_fuse",
            status="unobserved",
            evidence_kind="unavailable",
            reason=(
                linux_probe.reason
                if not linux_probe.present
                else "Linux FUSE doctor passed capability probe but this qualifier did not start a live kernel mount."
            ),
        ),
        _driver_operation(
            "windows_winfsp",
            status="unobserved",
            evidence_kind="unavailable",
            reason=windows_probe.reason,
        ),
        _driver_operation(
            "container_fuse",
            status="unobserved",
            evidence_kind="unavailable",
            reason=container_probe.reason,
        ),
    )

    live_observations = (
        _unobserved("linux_fuse", live_reason),
        _unobserved("windows_winfsp", live_reason),
        _unobserved("container_fuse", live_reason),
        _blocked(
            "interface_parity",
            reason=(
                "Hermetic VFS/WAL/current-root recovery was observed. "
                "CLI, MCP, and MCP++ VFS sessions were not exercised. "
                f"{PCPR_026_TASK_ID} owns interface parity."
            ),
            limitations=(
                "hermetic_observed" if hermetic_observed else "hermetic_failed",
                "cli_unavailable",
                "mcp_unavailable",
                "mcpp_unavailable",
            ),
        ),
        _blocked(
            "witness_key_protection",
            reason=(
                "Witness and proving-key protection is owned by the proof-seal "
                f"store ({PCPR_024_TASK_ID}). This receipt does not claim it."
            ),
            limitations=("deferred_to_pcpr_024",),
        ),
    )

    probes = (
        QualificationProbe(
            probe_id="hermetic_vfs_wal_adapter",
            present=hermetic_observed,
            evidence_kind="measured_hermetic" if hermetic_observed else "unavailable",
            live=False,
            simulated_represented_as_live=False,
            reason=(
                "HermeticVfsWalRecoveryAdapter executed current-root CAS, "
                "stale-parent rejection, concurrent writers, restart, WAL "
                "recovery, ARC coherence, crash recovery, tombstone, "
                "invalidation, corruption, and hermetic mount lifecycle."
                if hermetic_observed
                else "Hermetic VFS/WAL suite did not complete."
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
            },
        ),
        linux_probe,
        windows_probe,
        container_probe,
        *probe_cli_mcp_surfaces(),
        QualificationProbe(
            probe_id="proof_seal_not_in_scope",
            present=None,
            evidence_kind="unavailable",
            live=False,
            simulated_represented_as_live=False,
            reason=(
                f"Proof-seal store qualification is {PCPR_024_TASK_ID}. "
                "Witness and key protection stay typed unavailable."
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
                f"Authoritative support-matrix generation is {PCPR_027_TASK_ID}. "
                "This receipt does not replace it."
            ),
            details={"remediating_task": PCPR_027_TASK_ID},
        ),
        QualificationProbe(
            probe_id="iroh_not_in_scope",
            present=None,
            evidence_kind="unavailable",
            live=False,
            simulated_represented_as_live=False,
            reason=(
                f"Iroh qualification or de-scope is {PCPR_022_TASK_ID}. "
                "This receipt does not reopen it."
            ),
            details={"remediating_task": PCPR_022_TASK_ID},
        ),
    )

    hermetic_ops = tuple(
        _hermetic_operation(
            str(item["operation"]),
            status=str(item["status"]),
            reason=str(item.get("detail") or "hermetic VFS/WAL observation"),
            digests=item.get("digests") if isinstance(item.get("digests"), Mapping) else {},
        )
        for item in observations
    )
    python_ops = tuple(
        str(item["operation"])
        for item in observations
        if item.get("status") == "passed"
    )
    missing = tuple(
        operation
        for operation in REQUIRED_RECOVERY_OPERATIONS
        if operation not in python_ops
    )
    disposition = (
        CertificationDisposition.CONDITIONAL.value
        if hermetic_observed
        else CertificationDisposition.UNAVAILABLE.value
    )
    combined_observations = tuple(dict(item) for item in observations) + tuple(
        dict(item) for item in live_observations
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
        "vfs_live_qualified": False,
        "suite_complete": False,
        "certification_disposition": disposition,
        "support_class": SUPPORT_CLASS,
        "live_support_claim": False,
        "simulated_results_represented_as_live": False,
        "hermetic_results_represented_as_live": False,
        "hermetic_vfs_observed": hermetic_observed
        and set(python_ops) >= set(REQUIRED_RECOVERY_OPERATIONS),
        "linux_fuse_live_qualified": False,
        "windows_winfsp_live_qualified": False,
        "container_fuse_live_qualified": False,
        "interface_parity_qualified": False,
        "live_fuse_evidence_kind": "unavailable",
        "this_task_created_competing_authority": False,
        "probes": [item.to_mapping() for item in probes],
        "observations": list(combined_observations),
        "hermetic_operations": [dict(item) for item in hermetic_ops],
        "live_driver_operations": [dict(item) for item in live_driver_ops],
        "operations_observed": list(python_ops),
        "operations_missing": list(missing) + list(LIVE_DRIVER_OPERATIONS),
        "blockers": [],
    }
    _reject_closed_release_value(payload["promotion_status"], "promotion_status")
    _reject_closed_release_value(
        payload["supervisor_disposition"], "supervisor_disposition"
    )
    if payload["closed_release_outcome"] is not None:
        raise VfsWalQualificationError("closed_release_outcome must be null")
    if payload["promotion_status"] not in PROMOTION_STATUSES:
        raise VfsWalQualificationError("promotion_status is not admitted")
    if payload["promotion_status"] == "supervisor_promoted":
        raise VfsWalQualificationError("PCPR-023 cannot promote the supervisor")
    if payload["vfs_live_qualified"] is True:
        raise VfsWalQualificationError(
            "vfs_live_qualified cannot be true without live FUSE evidence"
        )
    if payload["live_support_claim"] is True:
        raise VfsWalQualificationError("live_support_claim cannot be true for PCPR-023")
    if payload["hermetic_results_represented_as_live"] is True:
        raise VfsWalQualificationError("hermetic results cannot be represented as live")
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
        vfs_live_qualified=False,
        suite_complete=False,
        certification_disposition=payload["certification_disposition"],
        support_class=SUPPORT_CLASS,
        live_support_claim=False,
        simulated_results_represented_as_live=False,
        hermetic_results_represented_as_live=False,
        hermetic_vfs_observed=bool(payload["hermetic_vfs_observed"]),
        linux_fuse_live_qualified=False,
        windows_winfsp_live_qualified=False,
        container_fuse_live_qualified=False,
        interface_parity_qualified=False,
        live_fuse_evidence_kind="unavailable",
        this_task_created_competing_authority=False,
        probes=probes,
        observations=tuple(payload["observations"]),
        hermetic_operations=tuple(payload["hermetic_operations"]),
        live_driver_operations=tuple(payload["live_driver_operations"]),
        operations_observed=tuple(payload["operations_observed"]),
        operations_missing=tuple(payload["operations_missing"]),
        blockers=(),
        verdict_cid=cid,
    )


def qualify_current_head_vfs_wal(
    *, now: datetime | None = None
) -> QualificationVerdict:
    return qualify_vfs_wal(now=now)


def validate_pcpr_023_outer_receipt(payload: Mapping[str, Any]) -> None:
    """Reject closed-release claims and simulated-as-live promotion."""

    if not isinstance(payload, Mapping):
        raise VfsWalQualificationError("receipt must be a mapping")
    task_id = _text(payload.get("task_id"), "task_id")
    if task_id != PCPR_023_TASK_ID:
        raise VfsWalQualificationError("task_id must be PCPR-023")
    promotion = None
    acceptance = payload.get("acceptance")
    verdict = payload.get("qualification_verdict")
    if isinstance(acceptance, Mapping):
        promotion = acceptance.get("promotion_status")
        if acceptance.get("closed_release_outcome") is not None:
            raise VfsWalQualificationError(
                "acceptance.closed_release_outcome must be null"
            )
        if acceptance.get("release_claim") is True:
            raise VfsWalQualificationError("acceptance.release_claim must be false")
        if acceptance.get("vfs_live_qualified") is True:
            raise VfsWalQualificationError(
                "acceptance.vfs_live_qualified cannot be true without live FUSE"
            )
    if isinstance(verdict, Mapping):
        promotion = verdict.get("promotion_status", promotion)
        if verdict.get("closed_release_outcome") is not None:
            raise VfsWalQualificationError(
                "qualification_verdict.closed_release_outcome must be null"
            )
        if verdict.get("vfs_live_qualified") is True:
            raise VfsWalQualificationError(
                "vfs_live_qualified cannot be true without live FUSE evidence"
            )
        if verdict.get("simulated_results_represented_as_live") is True:
            raise VfsWalQualificationError(
                "simulated results cannot be represented as live"
            )
        if verdict.get("hermetic_results_represented_as_live") is True:
            raise VfsWalQualificationError(
                "hermetic results cannot be represented as live"
            )
        if verdict.get("live_support_claim") is True:
            raise VfsWalQualificationError(
                "live_support_claim cannot be true without a complete live FUSE suite"
            )
        live_kind = verdict.get("live_fuse_evidence_kind")
        if live_kind is not None:
            _kind(live_kind, "live_fuse_evidence_kind")
    promotion_text = _text(promotion, "promotion_status")
    if promotion_text not in PROMOTION_STATUSES:
        raise VfsWalQualificationError("promotion_status is not admitted")
    if promotion_text in CLOSED_RELEASE_OUTCOMES:
        raise VfsWalQualificationError("promotion_status is a closed release outcome")
    legend = payload.get("evidence_legend")
    if legend is not None and not isinstance(legend, Mapping):
        raise VfsWalQualificationError(
            "evidence_legend must be a mapping when present"
        )


__all__ = [
    "QUALIFICATION_INTERFACE",
    "QUALIFICATION_SCHEMA",
    "QUALIFICATION_VERDICT_SCHEMA",
    "PCPR_023_TASK_ID",
    "PCPR_023_GOAL_ID",
    "CLOSED_RELEASE_OUTCOMES",
    "PROMOTION_STATUSES",
    "HERMETIC_CANDIDATE_SUITES",
    "REQUIRED_RECOVERY_OPERATIONS",
    "LIVE_DRIVER_OPERATIONS",
    "VfsWalQualificationError",
    "QualificationVerdict",
    "refuse_simulated_as_live",
    "refuse_hermetic_as_live",
    "sealed_which",
    "probe_linux_fuse",
    "run_hermetic_vfs_wal_suite",
    "qualify_vfs_wal",
    "qualify_current_head_vfs_wal",
    "validate_pcpr_023_outer_receipt",
    "observe_sealed_validation_environment",
]

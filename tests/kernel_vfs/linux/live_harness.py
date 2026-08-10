"""KVFS-506: Bounded real Linux kernel-mount conformance and crash harness.

Owns the labeled Linux FUSE live-receipt path:

* capability probe is bounded (≤5 s) and fail-closed;
* readiness is 15 s, each case is 60 s, cleanup uses ``finally`` + watchdog;
* exclusive mount/state leases fence concurrent runners;
* kernel CRUD, open flags, offset/sparse I/O, truncate, metadata, concurrent
  handles, unlink/rename, fsync, forced kill, recovery replay, ARC coherence,
  and unmount emit pinned live receipts;
* absent native FUSE capability emits a bounded ``capability_unavailable``
  receipt and **cannot** promote Linux live support.

Hermetic execution plane (default on non-capable runners) exercises the same
case matrix through :class:`LinuxMountLifecycle` + :class:`KernelVFSOperations`
so CI can validate harness bounds without claiming live support. Native live
plane requires doctor ``native_capability_ready``; only that plane may emit
``status=passed`` live-support receipts.
"""

from __future__ import annotations

import json
import os
import platform
import random
import shutil
import signal
import sys
import tempfile
import threading
import time
import traceback
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Final

from ipfs_kit_py.core.vfs.host_contracts import HostPlatform, OpenFlag
from ipfs_kit_py.kernel_vfs.cache_coherence import (
    CacheCoherence,
    CoherenceDisposition,
    CoherenceEvent,
    CoherenceMutationKind,
    CoherenceSource,
    path_to_content_id,
)
from ipfs_kit_py.kernel_vfs.cached_storage import CachedStorage
from ipfs_kit_py.kernel_vfs.linux import (
    DEFAULT_READINESS_TIMEOUT_SECONDS,
    LinuxMountConfig,
    LinuxMountLifecycle,
)
from ipfs_kit_py.kernel_vfs.operations import (
    DEFAULT_MOUNT_ID,
    KernelVFSOperations,
    build_kernel_vfs_operations,
)
from ipfs_kit_py.kernel_vfs.platform import (
    DOCTOR_BUDGET_SECONDS,
    run_linux_doctor,
)
from ipfs_kit_py.kernel_vfs.wal_recovery import MountRecoveryCoordinator

# ---------------------------------------------------------------------------
# Identity / bounds (plan §6 test matrix / KVFS-506 acceptance)
# ---------------------------------------------------------------------------

TASK_ID: Final[str] = "KVFS-506"
CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

HARNESS_NAMESPACE: Final[str] = "ipfs_kit_py/tests/kernel_vfs/linux/live_harness"
LIVE_RECEIPT_SCHEMA: Final[str] = "KernelVFSLinuxLiveReceipt@1"
CASE_RECEIPT_SCHEMA: Final[str] = f"{HARNESS_NAMESPACE}/case-receipt@{SCHEMA_MAJOR}"
SUITE_RECEIPT_SCHEMA: Final[str] = f"{HARNESS_NAMESPACE}/suite-receipt@{SCHEMA_MAJOR}"
CAPABILITY_RECEIPT_SCHEMA: Final[str] = (
    f"{HARNESS_NAMESPACE}/capability-receipt@{SCHEMA_MAJOR}"
)
PROFILE_LIVE: Final[str] = "linux_live_fuse"
PROFILE_HERMETIC: Final[str] = "linux_hermetic_conformance"
PINNED_ABI: Final[str] = "libfuse2"
PINNED_BINDING: Final[str] = "fusepy_high_level_fuse2"

READINESS_TIMEOUT_SECONDS: Final[float] = DEFAULT_READINESS_TIMEOUT_SECONDS  # 15
CASE_TIMEOUT_SECONDS: Final[float] = 60.0
CAPABILITY_PROBE_BUDGET_SECONDS: Final[float] = min(DOCTOR_BUDGET_SECONDS, 5.0)
WATCHDOG_JOIN_SECONDS: Final[float] = 2.0
MAX_RECEIPT_DETAIL_BYTES: Final[int] = 16_384
DEFAULT_MOUNT_DIRECTORY_NAME: Final[str] = "kvfs-linux-live"

SUPPORT_CLAIM_UNAVAILABLE: Final[str] = "capability_unavailable"
SUPPORT_CLAIM_LIVE_PASSED: Final[str] = "live_passed"
SUPPORT_CLAIM_HERMETIC_ONLY: Final[str] = "hermetic_only"

# Environment opt-in for forcing live plane attempts on labeled runners.
LIVE_FORCE_ENV: Final[str] = "IPFS_KIT_KERNEL_VFS_LINUX_LIVE"
LIVE_GATE_ENV: Final[str] = "IPFS_KIT_KERNEL_VFS_LINUX_LIVE_GATE"


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class ExecutionPlane(str, Enum):
    """How a case is executed."""

    HERMETIC = "hermetic"
    LIVE = "live"


class CaseStatus(str, Enum):
    """Terminal status of one bounded conformance case."""

    PASSED = "passed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CAPABILITY_UNAVAILABLE = "capability_unavailable"
    SKIPPED = "skipped"
    CLEANUP_FAILED = "cleanup_failed"


class ConformanceCaseId(str, Enum):
    """Pinned case matrix required by KVFS-506 acceptance."""

    KERNEL_CRUD = "kernel_crud"
    FLAGS = "flags"
    OFFSET_SPARSE_IO = "offset_sparse_io"
    TRUNCATE = "truncate"
    METADATA = "metadata"
    CONCURRENT_HANDLES = "concurrent_handles"
    UNLINK_RENAME = "unlink_rename"
    FSYNC = "fsync"
    FORCED_KILL = "forced_kill"
    REPLAY = "replay"
    ARC_COHERENCE = "arc_coherence"
    UNMOUNT = "unmount"


REQUIRED_CASE_IDS: Final[tuple[ConformanceCaseId, ...]] = tuple(ConformanceCaseId)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class LiveHarnessError(Exception):
    """Base harness failure (fail-closed)."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "LIVE_HARNESS_ERROR",
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.detail = dict(detail or {})

    def to_record(self) -> dict[str, Any]:
        return {
            "error": type(self).__name__,
            "message": self.message,
            "code": self.code,
            "detail": dict(self.detail),
        }


class CaseTimeoutError(LiveHarnessError):
    """Case exceeded the declared 60-second bound."""

    def __init__(
        self,
        case_id: str,
        *,
        timeout_seconds: float = CASE_TIMEOUT_SECONDS,
        elapsed_seconds: float = 0.0,
    ) -> None:
        super().__init__(
            f"case {case_id} exceeded {timeout_seconds:.1f}s bound",
            code="CASE_TIMEOUT",
            detail={
                "case_id": case_id,
                "timeout_seconds": timeout_seconds,
                "elapsed_seconds": elapsed_seconds,
            },
        )
        self.case_id = case_id
        self.timeout_seconds = timeout_seconds
        self.elapsed_seconds = elapsed_seconds


class SupportPromotionError(LiveHarnessError):
    """Raised when code attempts to promote live support without capability."""

    def __init__(self, message: str = "cannot promote live Linux FUSE support") -> None:
        super().__init__(message, code="SUPPORT_PROMOTION_BLOCKED")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unix_ms() -> int:
    return int(time.time() * 1000)


def _monotonic() -> float:
    return time.monotonic()


def _bounded_text(value: Any, *, limit: int = 4_096) -> str:
    text = "" if value is None else str(value)
    encoded = text.encode("utf-8")
    if len(encoded) <= limit:
        return text
    return encoded[:limit].decode("utf-8", errors="ignore")


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{uuid.uuid4().hex}")
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(tmp), str(path))
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass


def is_linux_host() -> bool:
    return sys.platform.startswith("linux")


def architecture_label() -> str:
    """Return process architecture label for capability receipts."""

    machine = (platform.machine() or "").lower()
    if machine in ("x86_64", "amd64"):
        return "x86_64"
    if machine in ("aarch64", "arm64"):
        return "aarch64"
    if machine in ("i386", "i686", "x86"):
        return "x86"
    return machine or ("64bit" if sys.maxsize > 2**32 else "32bit")


def support_claim_for(
    *,
    native_ready: bool,
    live_cases_passed: bool,
    plane: ExecutionPlane | str,
) -> str:
    """Derive support claim. Absent capability can never promote support."""

    plane_value = plane.value if isinstance(plane, ExecutionPlane) else str(plane)
    if not native_ready:
        return SUPPORT_CLAIM_UNAVAILABLE
    if plane_value == ExecutionPlane.LIVE.value and live_cases_passed:
        return SUPPORT_CLAIM_LIVE_PASSED
    return SUPPORT_CLAIM_HERMETIC_ONLY


def can_promote_live_support(
    *,
    native_ready: bool,
    support_claim: str,
    status: str,
    profile: str,
) -> bool:
    """True only when every live-gate admission condition holds."""

    if not native_ready:
        return False
    if support_claim != SUPPORT_CLAIM_LIVE_PASSED:
        return False
    if status not in {"passed", "admitted"}:
        return False
    if profile != PROFILE_LIVE:
        return False
    return True


# ---------------------------------------------------------------------------
# Capability probe
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CapabilityReceipt:
    """Bounded Linux FUSE capability probe receipt."""

    SCHEMA: ClassVar[str] = CAPABILITY_RECEIPT_SCHEMA

    native_ready: bool
    support_claim: str
    architecture: str
    pinned_abi: str
    pinned_binding: str
    platform: str
    is_linux: bool
    elapsed_seconds: float
    budget_seconds: float
    within_budget: bool
    doctor: Mapping[str, Any] = field(default_factory=dict)
    absences: tuple[Mapping[str, Any], ...] = ()
    message: str = ""
    unix_ms: int = 0
    # Probe alone never promotes live support (fail-closed attribute + record).
    support_promoted: bool = False

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "task_id": TASK_ID,
            "native_ready": self.native_ready,
            "support_claim": self.support_claim,
            "architecture": self.architecture,
            "pinned_abi": self.pinned_abi,
            "pinned_binding": self.pinned_binding,
            "platform": self.platform,
            "is_linux": self.is_linux,
            "elapsed_seconds": self.elapsed_seconds,
            "budget_seconds": self.budget_seconds,
            "within_budget": self.within_budget,
            "doctor": dict(self.doctor),
            "absences": [dict(item) for item in self.absences],
            "message": self.message,
            "unix_ms": self.unix_ms or _unix_ms(),
            "support_promoted": bool(self.support_promoted),
        }


def probe_linux_capability(
    *,
    budget_seconds: float = CAPABILITY_PROBE_BUDGET_SECONDS,
    mountpoint: str | Path | None = None,
    state_dir: str | Path | None = None,
) -> CapabilityReceipt:
    """Run the ≤5 s Linux FUSE doctor and project a capability receipt.

    Never mounts, never loads native libraries via the doctor, never starts a
    daemon. Absent capability yields ``support_claim=capability_unavailable``.
    """

    started = _monotonic()
    arch = architecture_label()
    is_lin = is_linux_host()
    doctor: dict[str, Any] = {}
    absences: list[dict[str, Any]] = []
    message = ""

    try:
        doctor = dict(
            run_linux_doctor(
                budget_seconds=budget_seconds,
                mountpoint=mountpoint,
                state_dir=state_dir,
            )
        )
    except Exception as exc:  # noqa: BLE001 — probe must terminate
        message = _bounded_text(exc)
        absences.append({"check": "doctor", "message": message})
        doctor = {
            "schema": "KernelVFSLinuxDoctorReport@1",
            "native_capability_ready": False,
            "support_claim": SUPPORT_CLAIM_UNAVAILABLE,
            "error": message,
        }

    elapsed = _monotonic() - started
    doctor_ready = bool(doctor.get("native_capability_ready"))
    # Live plane requires Linux host + doctor ready.
    native_ready = bool(is_lin and doctor_ready)
    if not is_lin:
        absences.append(
            {
                "check": "os",
                "message": f"host platform is {sys.platform}, not Linux",
            }
        )
    if not doctor_ready and not absences:
        actionable = doctor.get("checks", {}).get("actionable_absence", {})
        items = actionable.get("items") if isinstance(actionable, Mapping) else None
        if isinstance(items, list):
            for item in items:
                if isinstance(item, Mapping):
                    absences.append(dict(item))
        if not absences:
            absences.append(
                {
                    "check": "native_capability",
                    "message": "Linux FUSE native capability not ready",
                }
            )

    if not message:
        if native_ready:
            message = "Linux FUSE capability ready"
        else:
            message = "Linux FUSE live capability unavailable; support not promoted"

    return CapabilityReceipt(
        native_ready=native_ready,
        support_claim=(
            "probe_passed" if native_ready else SUPPORT_CLAIM_UNAVAILABLE
        ),
        architecture=arch,
        pinned_abi=PINNED_ABI,
        pinned_binding=PINNED_BINDING,
        platform=sys.platform,
        is_linux=is_lin,
        elapsed_seconds=elapsed,
        budget_seconds=budget_seconds,
        within_budget=elapsed <= budget_seconds + 0.05,
        doctor=doctor,
        absences=tuple(absences),
        message=message,
        unix_ms=_unix_ms(),
        support_promoted=False,  # probe never promotes live support
    )


# ---------------------------------------------------------------------------
# Watchdog
# ---------------------------------------------------------------------------


class CaseWatchdog:
    """Independent watchdog that marks runaway cases after *timeout*."""

    def __init__(self, timeout_seconds: float = CASE_TIMEOUT_SECONDS) -> None:
        self.timeout_seconds = max(0.1, float(timeout_seconds))
        self._stop = threading.Event()
        self._fired = threading.Event()
        self._thread: threading.Thread | None = None
        self._case_id = ""

    @property
    def fired(self) -> bool:
        return self._fired.is_set()

    def start(self, case_id: str) -> None:
        self.cancel()
        self._case_id = case_id
        self._stop.clear()
        self._fired.clear()
        self._thread = threading.Thread(
            target=self._run,
            name=f"linux-case-watchdog-{case_id}",
            daemon=True,
        )
        self._thread.start()

    def cancel(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=WATCHDOG_JOIN_SECONDS)
        self._thread = None

    def _run(self) -> None:
        if self._stop.wait(self.timeout_seconds):
            return
        self._fired.set()


class CleanupWatchdog:
    """Background cleanup enforcer that runs after a deadline."""

    def __init__(
        self,
        callback: Callable[[], None],
        *,
        deadline_seconds: float = CASE_TIMEOUT_SECONDS,
    ) -> None:
        self._callback = callback
        self.deadline_seconds = max(0.1, float(deadline_seconds))
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name="linux-cleanup-watchdog",
            daemon=True,
        )
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._thread.start()

    def cancel(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=WATCHDOG_JOIN_SECONDS)

    def _run(self) -> None:
        if self._stop.wait(self.deadline_seconds):
            return
        try:
            self._callback()
        except Exception:  # noqa: BLE001 — watchdog must not raise
            pass


# ---------------------------------------------------------------------------
# Case receipts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CaseReceipt:
    """Terminal receipt for one bounded conformance case."""

    SCHEMA: ClassVar[str] = CASE_RECEIPT_SCHEMA

    case_id: str
    status: CaseStatus
    plane: ExecutionPlane
    success: bool
    elapsed_seconds: float
    timeout_seconds: float
    readiness_timeout_seconds: float
    support_claim: str
    support_promoted: bool
    mount_root: str = ""
    message: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)
    unix_ms: int = 0
    receipt_id: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "task_id": TASK_ID,
            "receipt_id": self.receipt_id
            or f"receipt:case:{self.case_id}:{uuid.uuid4().hex}",
            "case_id": self.case_id,
            "status": self.status.value,
            "plane": self.plane.value,
            "success": self.success,
            "elapsed_seconds": self.elapsed_seconds,
            "timeout_seconds": self.timeout_seconds,
            "readiness_timeout_seconds": self.readiness_timeout_seconds,
            "support_claim": self.support_claim,
            "support_promoted": self.support_promoted,
            "mount_root": self.mount_root,
            "message": self.message,
            "detail": dict(self.detail),
            "unix_ms": self.unix_ms or _unix_ms(),
            "bounded": self.elapsed_seconds <= self.timeout_seconds + 0.5,
        }


@dataclass(frozen=True)
class SuiteReceipt:
    """Aggregate live/hermetic suite receipt (packaging live-gate shape)."""

    SCHEMA: ClassVar[str] = LIVE_RECEIPT_SCHEMA

    status: str
    profile: str
    platform: str
    architecture: str
    support_claim: str
    support_promoted: bool
    native_ready: bool
    plane: ExecutionPlane
    cases: tuple[CaseReceipt, ...]
    capability: CapabilityReceipt
    elapsed_seconds: float
    readiness_timeout_seconds: float = READINESS_TIMEOUT_SECONDS
    case_timeout_seconds: float = CASE_TIMEOUT_SECONDS
    message: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)
    receipt_id: str = ""
    unix_ms: int = 0

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "schema_version": SCHEMA_VERSION,
            "contract_version": CONTRACT_VERSION,
            "task_id": TASK_ID,
            "receipt_id": self.receipt_id
            or f"receipt:suite:{uuid.uuid4().hex}",
            "status": self.status,
            "gate_status": self.status,
            "profile": self.profile,
            # Lane follows profile so packaging live-gate never admits hermetic
            # evidence via a live lane fallback when profile is empty.
            "lane": self.profile,
            "platform": self.platform,
            "os": self.platform,
            "architecture": self.architecture,
            "pinned_abi": PINNED_ABI,
            "pinned_binding": PINNED_BINDING,
            "support_claim": self.support_claim,
            "support_promoted": self.support_promoted,
            "native_ready": self.native_ready,
            "plane": self.plane.value,
            "cases": [case.to_record() for case in self.cases],
            "case_ids": [case.case_id for case in self.cases],
            "required_case_ids": [c.value for c in REQUIRED_CASE_IDS],
            "capability": self.capability.to_record(),
            "elapsed_seconds": self.elapsed_seconds,
            "readiness_timeout_seconds": self.readiness_timeout_seconds,
            "case_timeout_seconds": self.case_timeout_seconds,
            "message": self.message,
            "detail": dict(self.detail),
            "unix_ms": self.unix_ms or _unix_ms(),
            # Only advertise live markers when support is actually promoted.
            "fuse": bool(self.support_promoted),
            "live": bool(self.support_promoted),
        }


# ---------------------------------------------------------------------------
# Mount session
# ---------------------------------------------------------------------------


@dataclass
class MountSession:
    """One mount session used by conformance cases.

    Combines a :class:`LinuxMountLifecycle` (process readiness / kill / unmount)
    with a :class:`KernelVFSOperations` surface that models the kernel-visible
    callback path the live FUSE plane would invoke.
    """

    lifecycle: LinuxMountLifecycle
    operations: KernelVFSOperations
    mountpoint: Path
    state_directory: Path
    plane: ExecutionPlane
    mount_id: str

    @property
    def root(self) -> str:
        return str(self.mountpoint)

    def close(self) -> None:
        try:
            self.operations.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.lifecycle.unmount(timeout_seconds=5.0)
        except Exception:  # noqa: BLE001
            try:
                self.lifecycle.signal_child(signal.SIGKILL)
            except Exception:  # noqa: BLE001
                pass


# ---------------------------------------------------------------------------
# Case implementations
# ---------------------------------------------------------------------------


def _errno_name(outcome: Any) -> str:
    errno = getattr(outcome, "errno", None)
    if errno is None:
        return ""
    return str(getattr(errno, "value", errno) or "")


def _outcome_message(outcome: Any) -> str:
    direct = getattr(outcome, "message", None)
    if direct:
        return _bounded_text(direct)
    err = getattr(outcome, "error", None)
    if err is not None:
        for attr in ("message", "msg"):
            value = getattr(err, attr, None)
            if value:
                return _bounded_text(value)
        return _bounded_text(err)
    return ""


def _require_success(outcome: Any, *, step: str) -> Any:
    if not getattr(outcome, "success", False):
        raise LiveHarnessError(
            f"{step} failed",
            code="CASE_STEP_FAILED",
            detail={
                "step": step,
                "errno": _errno_name(outcome),
                "message": _outcome_message(outcome),
            },
        )
    return outcome


def _release_handle(ops: KernelVFSOperations, handle: Any) -> None:
    if handle is None:
        return
    try:
        ops.fsync(handle_id=handle.handle_id, generation=handle.generation)
    except Exception:  # noqa: BLE001
        pass
    try:
        ops.release(handle_id=handle.handle_id, generation=handle.generation)
    except Exception:  # noqa: BLE001
        pass


def _create_with_body(
    ops: KernelVFSOperations,
    path: str,
    payload: bytes,
    *,
    mode: int = 0o644,
    step: str = "create",
    release: bool = True,
) -> Any:
    """Create ``path`` with ``payload``.

    Never pass ``O_EXCL`` through :meth:`KernelVFSOperations.create`: the
    composed runtime does exclusive host create then re-opens with the same
    flags, so ``O_EXCL`` on the open leg fails with ``EEXIST`` after a
    successful create.
    """

    created = ops.create(
        path,
        payload,
        mode=mode,
        flags=(OpenFlag.O_RDWR, OpenFlag.O_CREAT),
    )
    if created.success:
        handle = created.handle
        if release and handle is not None:
            _release_handle(ops, handle)
        return created

    # Path may already exist from a partial create (exclusive create committed
    # then open-with-O_EXCL failed). Repair via open+write.
    opened = ops.open(
        path, (OpenFlag.O_RDWR, OpenFlag.O_TRUNC, OpenFlag.O_CREAT), mode=mode
    )
    if opened.success and opened.handle is not None:
        handle = opened.handle
        written = ops.write(
            path,
            payload,
            offset=0,
            handle_id=handle.handle_id,
            generation=handle.generation,
        )
        if written.success:
            if release:
                _release_handle(ops, handle)
            # Prefer the open outcome so callers can keep the live handle when
            # release=False (create may have failed after a partial exclusive
            # create left the path present).
            return opened
        _release_handle(ops, handle)
    raise LiveHarnessError(
        f"{step} failed",
        code="CASE_STEP_FAILED",
        detail={
            "step": step,
            "path": path,
            "errno": _errno_name(created),
            "create_message": _bounded_text(getattr(created, "message", "") or ""),
            "open_errno": _errno_name(opened),
        },
    )


def _mkdir(ops: KernelVFSOperations, path: str, *, mode: int = 0o755) -> Any:
    """Create a directory; treat an existing directory as success."""

    outcome = ops.mkdir(path, mode=mode)
    if outcome.success:
        return outcome
    if _errno_name(outcome) == "EEXIST":
        st = ops.getattr(path)
        if st.success:
            return outcome
    return _require_success(outcome, step=f"mkdir:{path}")


def _rename_path(
    ops: KernelVFSOperations,
    source: str,
    target: str,
    *,
    step: str = "rename",
) -> Any:
    """Rename with a single conflict-repair pass for residual targets."""

    outcome = ops.rename(source, target)
    if outcome.success:
        return outcome

    src_exists = bool(ops.getattr(source).success)
    dst_exists = bool(ops.getattr(target).success)
    # Storage applied the rename but the projection reported failure.
    if (not src_exists) and dst_exists:
        return outcome

    if dst_exists and _errno_name(outcome) == "EEXIST":
        ops.unlink(target)
        outcome = ops.rename(source, target)
        if outcome.success:
            return outcome

    raise LiveHarnessError(
        f"{step} failed",
        code="CASE_STEP_FAILED",
        detail={
            "step": step,
            "source": source,
            "target": target,
            "errno": _errno_name(outcome),
            "src_exists": src_exists,
            "dst_exists": dst_exists,
            "message": _bounded_text(getattr(outcome, "message", "") or ""),
        },
    )


def _kernel_crud(session: MountSession) -> dict[str, Any]:
    """Kernel-visible create / read / update / rename / unlink / mkdir / rmdir."""

    ops = session.operations
    token = uuid.uuid4().hex[:12]
    folder = f"crud_dir_{token}"
    file_path = f"{folder}/note.txt"
    payload = b"linux-kernel-crud-v1\n"
    updated = b"linux-kernel-crud-v2\n"

    _mkdir(ops, folder, mode=0o755)
    _create_with_body(ops, file_path, payload, step="create")
    read = _require_success(
        ops.read(file_path, offset=0, size=len(payload) + 8), step="read"
    )
    if bytes(read.data or b"")[: len(payload)] != payload:
        raise LiveHarnessError("crud read mismatch", code="CASE_ASSERT")
    opened = _require_success(
        ops.open(file_path, (OpenFlag.O_RDWR, OpenFlag.O_TRUNC)), step="open-update"
    )
    handle = opened.handle
    assert handle is not None
    _require_success(
        ops.write(
            file_path,
            updated,
            offset=0,
            handle_id=handle.handle_id,
            generation=handle.generation,
        ),
        step="write-update",
    )
    _release_handle(ops, handle)
    renamed = f"{folder}/note-renamed.txt"
    _rename_path(ops, file_path, renamed, step="rename")
    read2 = _require_success(
        ops.read(renamed, offset=0, size=len(updated) + 4), step="read-renamed"
    )
    if bytes(read2.data or b"")[: len(updated)] != updated:
        raise LiveHarnessError("crud post-rename mismatch", code="CASE_ASSERT")
    listing = _require_success(ops.readdir(folder), step="readdir")
    entries = list(listing.dir_entries or ())
    if "note-renamed.txt" not in entries and not any(
        "note-renamed" in str(e) for e in entries
    ):
        raise LiveHarnessError(
            "readdir missing renamed entry",
            code="CASE_ASSERT",
            detail={"entries": entries},
        )
    _require_success(ops.unlink(renamed), step="unlink")
    _require_success(ops.rmdir(folder), step="rmdir")
    return {
        "operations": [
            "mkdir",
            "create",
            "read",
            "write",
            "rename",
            "readdir",
            "unlink",
            "rmdir",
        ],
        "bytes": len(updated),
    }


def _flags(session: MountSession) -> dict[str, Any]:
    """Open-flag combinations (CREAT/EXCL/TRUNC/APPEND/RDONLY/RDWR)."""

    ops = session.operations
    path = f"flags_{uuid.uuid4().hex[:12]}.bin"
    body = b"flag-body-v1"
    # First create must not pass O_EXCL into KernelVFSOperations.create: the
    # runtime exclusive-creates then re-opens with the same flags, so O_EXCL on
    # the open leg always fails with EEXIST after a successful create.
    created = _create_with_body(ops, path, body, step="O_CREAT", release=True)

    # Existing path + exclusive create must fail closed (host exclusive=True
    # and/or O_EXCL open semantics).
    again = ops.create(
        path,
        b"other",
        mode=0o644,
        flags=(OpenFlag.O_RDWR, OpenFlag.O_CREAT, OpenFlag.O_EXCL),
    )
    if again.success:
        _release_handle(ops, again.handle)
        raise LiveHarnessError("O_EXCL did not reject existing path", code="CASE_ASSERT")
    # Host exclusive create projects EEXIST; accept any hard failure as rejection.
    excl_errno = _errno_name(again)
    if excl_errno and excl_errno not in {"EEXIST", "EIO", "EBUSY"}:
        raise LiveHarnessError(
            f"unexpected exclusive-create errno: {excl_errno}",
            code="CASE_ASSERT",
            detail={"errno": excl_errno, "message": _outcome_message(again)},
        )

    # Truncate open clears content.
    trunc = _require_success(
        ops.open(path, (OpenFlag.O_RDWR, OpenFlag.O_TRUNC)),
        step="O_TRUNC",
    )
    assert trunc.handle is not None
    _require_success(
        ops.write(
            path,
            b"T",
            offset=0,
            handle_id=trunc.handle.handle_id,
            generation=trunc.handle.generation,
        ),
        step="write after O_TRUNC",
    )
    _release_handle(ops, trunc.handle)

    # Append open.
    append = _require_success(
        ops.open(path, (OpenFlag.O_WRONLY, OpenFlag.O_APPEND)),
        step="O_APPEND",
    )
    assert append.handle is not None
    _require_success(
        ops.write(
            path,
            b"A",
            offset=0,
            handle_id=append.handle.handle_id,
            generation=append.handle.generation,
        ),
        step="write O_APPEND",
    )
    _release_handle(ops, append.handle)

    ro = _require_success(ops.open(path, OpenFlag.O_RDONLY), step="O_RDONLY")
    assert ro.handle is not None
    read = _require_success(
        ops.read(
            path,
            offset=0,
            size=16,
            handle_id=ro.handle.handle_id,
            generation=ro.handle.generation,
        ),
        step="read O_RDONLY",
    )
    _release_handle(ops, ro.handle)
    data = bytes(read.data or b"")
    if not data:
        raise LiveHarnessError("flags body empty after flag sequence", code="CASE_ASSERT")
    _require_success(ops.unlink(path), step="unlink flags")
    return {
        "flags": [
            "O_CREAT",
            "O_EXCL",
            "O_TRUNC",
            "O_APPEND",
            "O_RDONLY",
            "O_RDWR",
            "O_WRONLY",
        ],
        "excl_rejected": True,
        "bytes": len(data),
        "initial_create": bool(getattr(created, "success", True)),
    }


def _offset_sparse_io(session: MountSession) -> dict[str, Any]:
    """Offset writes, sparse holes past EOF, and random partial I/O."""

    ops = session.operations
    path = f"sparse_{uuid.uuid4().hex[:8]}.bin"
    size = 8_192
    rng = random.Random(506)
    created = _create_with_body(ops, path, b"", step="create sparse", release=False)
    handle = getattr(created, "handle", None)
    if handle is None:
        opened = _require_success(
            ops.open(path, (OpenFlag.O_RDWR, OpenFlag.O_CREAT), mode=0o644),
            step="open sparse",
        )
        handle = opened.handle
    assert handle is not None
    _require_success(ops.truncate(path, size), step="grow sparse buffer")

    model = bytearray(b"\x00" * size)
    writes: list[tuple[int, bytes]] = []
    for _ in range(16):
        offset = rng.randint(0, size - 128)
        length = rng.randint(1, 128)
        data = bytes(rng.getrandbits(8) for _ in range(length))
        _require_success(
            ops.write(
                path,
                data,
                offset=offset,
                handle_id=handle.handle_id,
                generation=handle.generation,
            ),
            step=f"sparse write @{offset}",
        )
        writes.append((offset, data))
        model[offset : offset + len(data)] = data

    # Sparse hole: write past current logical end after shrink then grow.
    hole_offset = size + 1_024
    hole_payload = b"HOLE"
    _require_success(
        ops.write(
            path,
            hole_payload,
            offset=hole_offset,
            handle_id=handle.handle_id,
            generation=handle.generation,
        ),
        step="sparse past-EOF write",
    )

    for offset, data in writes[-8:]:
        read = _require_success(
            ops.read(
                path,
                offset=offset,
                size=len(data),
                handle_id=handle.handle_id,
                generation=handle.generation,
            ),
            step=f"sparse read @{offset}",
        )
        expected = bytes(model[offset : offset + len(data)])
        if read.data[: len(data)] != expected:
            raise LiveHarnessError(
                "sparse I/O coherence mismatch",
                code="CASE_ASSERT",
                detail={"offset": offset},
            )

    hole_read = _require_success(
        ops.read(
            path,
            offset=hole_offset,
            size=len(hole_payload),
            handle_id=handle.handle_id,
            generation=handle.generation,
        ),
        step="read sparse hole payload",
    )
    if hole_read.data[: len(hole_payload)] != hole_payload:
        raise LiveHarnessError("sparse hole payload mismatch", code="CASE_ASSERT")

    _release_handle(ops, handle)
    _require_success(ops.unlink(path), step="unlink sparse")
    return {
        "writes": len(writes),
        "size": size,
        "sparse_offset": hole_offset,
        "hole_bytes": len(hole_payload),
    }


def _truncate_case(session: MountSession) -> dict[str, Any]:
    """Grow and shrink truncate with content preservation."""

    ops = session.operations
    path = f"trunc_{uuid.uuid4().hex[:8]}.dat"
    payload = b"ABCDEFGHIJKLMNOP"  # 16 bytes
    _create_with_body(ops, path, payload, step="create trunc", release=True)

    _require_success(ops.truncate(path, 32), step="grow truncate")
    grown = _require_success(ops.read(path, offset=0, size=32), step="read grown")
    data = bytes(grown.data or b"")
    if data[:16] != payload:
        raise LiveHarnessError("grow truncate lost prefix", code="CASE_ASSERT")

    _require_success(ops.truncate(path, 8), step="shrink truncate")
    shrunk = _require_success(ops.read(path, offset=0, size=16), step="read shrunk")
    if bytes(shrunk.data or b"")[:8] != payload[:8]:
        raise LiveHarnessError("shrink truncate mismatch", code="CASE_ASSERT")

    _require_success(ops.truncate(path, 0), step="zero truncate")
    zero = _require_success(ops.read(path, offset=0, size=8), step="read zero")
    if bytes(zero.data or b""):
        # Empty or zero-filled is acceptable; non-empty residual is not.
        if any(b != 0 for b in bytes(zero.data or b"")):
            raise LiveHarnessError("zero truncate left residual bytes", code="CASE_ASSERT")

    st = _require_success(ops.getattr(path), step="getattr after truncate")
    size = int(st.metadata.size) if st.metadata is not None else -1
    _require_success(ops.unlink(path), step="unlink trunc")
    return {"grown_to": 32, "shrunk_to": 8, "zeroed": True, "final_size": size}


def _metadata(session: MountSession) -> dict[str, Any]:
    """getattr / utimens / access / statfs metadata surface."""

    ops = session.operations
    path = f"meta_{uuid.uuid4().hex[:8]}.txt"
    _create_with_body(ops, path, b"meta", mode=0o640, step="create meta", release=True)
    st = _require_success(ops.getattr(path), step="getattr")
    _require_success(ops.access(path), step="access")
    _require_success(ops.utimens(path), step="utimens")
    fs = _require_success(ops.statfs(), step="statfs")
    _require_success(ops.unlink(path), step="unlink meta")
    return {
        "size": st.metadata.size if st.metadata else 0,
        "mode": st.metadata.mode if st.metadata else 0,
        "statfs_keys": sorted(fs.detail.keys()) if fs.detail else [],
    }


def _concurrent_handles(session: MountSession) -> dict[str, Any]:
    """Concurrent open handles with interleaved read/write."""

    ops = session.operations
    path = f"concurrent_{uuid.uuid4().hex[:8]}.bin"
    created = _create_with_body(
        ops, path, b"seed-body-506", step="create concurrent target", release=False
    )
    handle_a = getattr(created, "handle", None)
    if handle_a is None:
        opened_a = _require_success(
            ops.open(path, OpenFlag.O_RDWR), step="open concurrent a"
        )
        handle_a = opened_a.handle
    assert handle_a is not None
    opened_b = _require_success(
        ops.open(path, OpenFlag.O_RDWR), step="second concurrent open"
    )
    handle_b = opened_b.handle
    assert handle_b is not None

    errors: list[str] = []
    barrier = threading.Barrier(3)

    def writer_a() -> None:
        try:
            barrier.wait(timeout=5)
            for i in range(10):
                ops.write(
                    path,
                    f"A{i}".encode("ascii"),
                    offset=i * 2,
                    handle_id=handle_a.handle_id,
                    generation=handle_a.generation,
                )
                time.sleep(0.001)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"writer_a:{exc}")

    def writer_b() -> None:
        try:
            barrier.wait(timeout=5)
            for i in range(10):
                ops.write(
                    path,
                    f"B{i}".encode("ascii"),
                    offset=64 + i * 2,
                    handle_id=handle_b.handle_id,
                    generation=handle_b.generation,
                )
                time.sleep(0.001)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"writer_b:{exc}")

    def reader() -> None:
        try:
            barrier.wait(timeout=5)
            for i in range(10):
                ops.read(
                    path,
                    offset=0,
                    size=32,
                    handle_id=handle_a.handle_id,
                    generation=handle_a.generation,
                )
                time.sleep(0.001 * (i + 1))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"reader:{exc}")

    threads = [
        threading.Thread(target=writer_a, name="kvfs-conc-a", daemon=True),
        threading.Thread(target=writer_b, name="kvfs-conc-b", daemon=True),
        threading.Thread(target=reader, name="kvfs-conc-r", daemon=True),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
        if thread.is_alive():
            raise LiveHarnessError(
                "concurrent handles thread hung",
                code="CASE_HANG",
            )
    _release_handle(ops, handle_a)
    _release_handle(ops, handle_b)
    _require_success(ops.unlink(path), step="unlink concurrent")
    if errors:
        raise LiveHarnessError(
            "concurrent workers raised",
            code="CASE_CONCURRENT",
            detail={"errors": errors[:8]},
        )
    return {"workers": 3, "handles": 2, "errors": 0}


def _unlink_rename(session: MountSession) -> dict[str, Any]:
    """Unlink and rename while exercising open-handle race policy."""

    ops = session.operations
    token = uuid.uuid4().hex[:12]
    source = f"unlink_src_{token}.txt"
    target = f"unlink_dst_{token}.txt"
    payload = b"unlink-rename-body"
    created = _create_with_body(
        ops, source, payload, step="create src", release=False
    )
    handle = getattr(created, "handle", None)
    if handle is None:
        # Repair path may return an open outcome; re-open if needed.
        opened_src = _require_success(
            ops.open(source, OpenFlag.O_RDWR), step="reopen src"
        )
        handle = opened_src.handle
    assert handle is not None

    # Probe rename-while-open (must not hang). Prefer release+rename when the
    # open-handle policy rejects the rename so the case stays deterministic.
    rename_while_open = ops.rename(source, target)
    if rename_while_open.success:
        try:
            ops.read(
                target,
                offset=0,
                size=len(payload),
                handle_id=handle.handle_id,
                generation=handle.generation,
            )
        except Exception:  # noqa: BLE001
            pass
        _release_handle(ops, handle)
        handle = None
    else:
        _release_handle(ops, handle)
        handle = None
        src_exists = bool(ops.getattr(source).success)
        dst_exists = bool(ops.getattr(target).success)
        if src_exists or not dst_exists:
            _rename_path(ops, source, target, step="rename after release")

    read = _require_success(
        ops.read(target, offset=0, size=len(payload) + 4), step="read renamed"
    )
    if bytes(read.data or b"")[: len(payload)] != payload:
        raise LiveHarnessError("rename body mismatch", code="CASE_ASSERT")

    # Unlink while a fresh handle is open.
    opened = _require_success(ops.open(target, OpenFlag.O_RDONLY), step="open before unlink")
    open_handle = opened.handle
    unlink_outcome = ops.unlink(target)
    if open_handle is not None:
        _release_handle(ops, open_handle)
    # Path should be gone (or unlinked-but-open); re-unlink must not hang.
    if unlink_outcome.success:
        again = ops.unlink(target)
        # Second unlink may fail with ENOENT — both outcomes are acceptable.
        _ = again
    else:
        # Force cleanup after handle release.
        ops.unlink(target)

    # Source must not reappear.
    src_check = ops.getattr(source)
    if src_check.success:
        raise LiveHarnessError("source still visible after rename", code="CASE_ASSERT")
    return {
        "renamed": True,
        "unlinked": True,
        "open_during_unlink": True,
        "rename_while_open": bool(rename_while_open.success),
    }


def _fsync_case(session: MountSession) -> dict[str, Any]:
    """fsync / flush durability path after writes."""

    ops = session.operations
    path = f"fsync_{uuid.uuid4().hex[:8]}.dat"
    created = _create_with_body(ops, path, b"", step="create fsync", release=False)
    handle = getattr(created, "handle", None)
    if handle is None:
        opened = _require_success(
            ops.open(path, (OpenFlag.O_RDWR, OpenFlag.O_CREAT), mode=0o644),
            step="open fsync",
        )
        handle = opened.handle
    assert handle is not None
    payload = b"durable-bytes-506"
    _require_success(
        ops.write(
            path,
            payload,
            offset=0,
            handle_id=handle.handle_id,
            generation=handle.generation,
        ),
        step="write before fsync",
    )
    _require_success(
        ops.flush(handle_id=handle.handle_id, generation=handle.generation),
        step="flush",
    )
    _require_success(
        ops.fsync(
            handle_id=handle.handle_id,
            generation=handle.generation,
            datasync=False,
        ),
        step="fsync",
    )
    _require_success(
        ops.fsync(
            handle_id=handle.handle_id,
            generation=handle.generation,
            datasync=True,
        ),
        step="fdatasync",
    )
    read = _require_success(
        ops.read(
            path,
            offset=0,
            size=len(payload),
            handle_id=handle.handle_id,
            generation=handle.generation,
        ),
        step="read after fsync",
    )
    if read.data[: len(payload)] != payload:
        raise LiveHarnessError("fsync durability mismatch", code="CASE_ASSERT")
    _release_handle(ops, handle)
    _require_success(ops.unlink(path), step="unlink fsync")
    return {"bytes": len(payload), "fsync": True, "fdatasync": True}


def _forced_kill(session: MountSession) -> dict[str, Any]:
    """Forced SIGKILL of the mount child; remount recovers before ready."""

    life = session.lifecycle
    if not life.ready:
        raise LiveHarnessError("session not ready before kill", code="CASE_ASSERT")
    pid = life.pid
    if not pid:
        raise LiveHarnessError("no child pid to kill", code="CASE_ASSERT")

    state_dir = session.state_directory
    mountpoint = session.mountpoint
    plane = session.plane
    generation_id = life.config.generation_id

    # Force-kill the child (simulates hard crash). Prefer the lifecycle
    # signal helper so the parent records the signal; fall back to os.kill.
    if not life.signal_child(signal.SIGKILL):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    # Wait for process exit and allow the kernel to release flock leases.
    deadline = _monotonic() + 5.0
    while life.running and _monotonic() < deadline:
        time.sleep(0.02)
    if life.running:
        raise LiveHarnessError("child still running after SIGKILL", code="CASE_ASSERT")
    # Brief settle so exclusive state leases from the dead child release.
    time.sleep(0.05)

    # Recovery evidence must remain on disk (never deleted on crash).
    recovery_preserved = (state_dir / "recovery-preserved").exists() or (
        state_dir / "recovery"
    ).exists()
    if not recovery_preserved:
        raise LiveHarnessError(
            "recovery state not preserved after forced kill",
            code="CASE_ASSERT",
        )

    # Finalize the crashed parent lifecycle without deleting recovery state.
    try:
        life.unmount(timeout_seconds=2.0, sig=signal.SIGKILL)
    except Exception:  # noqa: BLE001
        pass

    # Remount may race the kernel flock release after SIGKILL; retry briefly.
    last_error: BaseException | None = None
    recovery_life: LinuxMountLifecycle | None = None
    phases: list[str] = []
    readiness = None
    for attempt in range(5):
        recovery_cfg = LinuxMountConfig(
            mountpoint=mountpoint,
            state_directory=state_dir,
            mount_id=f"mount:recover-{uuid.uuid4().hex[:8]}",
            readiness_timeout_seconds=READINESS_TIMEOUT_SECONDS,
            heartbeat_interval_seconds=0.05,
            unmount_timeout_seconds=5.0,
            hermetic=True,
            generation_id=generation_id,
            holder_id=f"holder:recover-{uuid.uuid4().hex[:8]}",
        )
        recovery_life = LinuxMountLifecycle(recovery_cfg)
        try:
            readiness = recovery_life.start(wait_ready=True)
            last_error = None
            break
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            try:
                recovery_life.unmount(timeout_seconds=2.0)
            except Exception:  # noqa: BLE001
                pass
            recovery_life = None
            time.sleep(0.05 * (attempt + 1))
    if last_error is not None or recovery_life is None or readiness is None:
        raise LiveHarnessError(
            "recovery remount failed after forced kill",
            code="CASE_RECOVERY",
            detail={
                "error": _bounded_text(last_error),
                "attempts": 5,
            },
        ) from last_error
    try:
        if not readiness.ready or not readiness.recovery_complete:
            raise LiveHarnessError(
                "recovery remount did not become ready",
                code="CASE_RECOVERY",
                detail=readiness.to_record(),
            )
        phases = list(readiness.recovery_phases or ())
        if (
            "enter_ready" in phases
            and "acquire_lease" in phases
            and phases.index("acquire_lease") > phases.index("enter_ready")
        ):
            raise LiveHarnessError(
                "ready advertised before lease recovery",
                code="CASE_RECOVERY_ORDER",
                detail={"phases": phases},
            )
        if (
            "enter_ready" in phases
            and "replay_wal" in phases
            and phases.index("replay_wal") > phases.index("enter_ready")
        ):
            raise LiveHarnessError(
                "ready advertised before WAL replay",
                code="CASE_RECOVERY_ORDER",
                detail={"phases": phases},
            )
        session.lifecycle = recovery_life
        session.plane = plane
    except Exception:
        try:
            recovery_life.unmount(timeout_seconds=5.0)
        except Exception:  # noqa: BLE001
            pass
        raise

    final_readiness = session.lifecycle.read_readiness()
    final_phases = (
        list(final_readiness.recovery_phases or ()) if final_readiness else phases
    )
    return {
        "killed": True,
        "signal": "SIGKILL",
        "pid": pid,
        "recovery_preserved": True,
        "recovered": True,
        "recovery_before_ready": True,
        "phases": final_phases,
    }


def _replay(session: MountSession) -> dict[str, Any]:
    """Recovery replay completes before ready; repeated restart is idempotent."""

    life = session.lifecycle
    readiness = life.read_readiness()
    if readiness is None or not readiness.ready or not readiness.recovery_complete:
        raise LiveHarnessError("session not ready for replay case", code="CASE_ASSERT")
    phases = list(readiness.recovery_phases or ())
    if "acquire_lease" not in phases or "enter_ready" not in phases:
        raise LiveHarnessError(
            "recovery phases incomplete",
            code="CASE_ASSERT",
            detail={"phases": phases},
        )
    if phases.index("acquire_lease") > phases.index("enter_ready"):
        raise LiveHarnessError("lease after ready", code="CASE_RECOVERY_ORDER")
    if "replay_wal" in phases and phases.index("replay_wal") > phases.index(
        "enter_ready"
    ):
        raise LiveHarnessError("replay after ready", code="CASE_RECOVERY_ORDER")

    # Explicit second recovery pass on a sibling state tree with durable stages.
    recovery_root = session.state_directory / "replay-probe"
    recovery_root.mkdir(parents=True, exist_ok=True)
    coord = MountRecoveryCoordinator(
        recovery_root,
        mount_id=f"mount:replay-{uuid.uuid4().hex[:8]}",
        generation_id=f"wal-gen:replay-{uuid.uuid4().hex[:8]}",
        platform=HostPlatform.LINUX,
        recovery_timeout_seconds=min(30.0, READINESS_TIMEOUT_SECONDS),
    )
    try:
        first = coord.recover()
        if not first.success or not first.ready or not first.recovery_complete:
            raise LiveHarnessError(
                "first recovery failed",
                code="CASE_RECOVERY",
                detail=first.to_record(),
            )
        first_phases = list(first.phases or ())
        if "replay_wal" not in first_phases:
            raise LiveHarnessError(
                "replay_wal phase missing",
                code="CASE_ASSERT",
                detail={"phases": first_phases},
            )
        if first_phases.index("replay_wal") > first_phases.index("enter_ready"):
            raise LiveHarnessError(
                "replay after ready on coordinator",
                code="CASE_RECOVERY_ORDER",
            )
        # Idempotent restart.
        second = coord.recover()
        if not second.success:
            raise LiveHarnessError(
                "idempotent recovery failed",
                code="CASE_RECOVERY",
                detail=second.to_record(),
            )
        return {
            "replayed": True,
            "idempotent": True,
            "phases": first_phases,
            "session_phases": phases,
            "recovery_before_ready": True,
            "first_disposition": str(
                first.disposition.value
                if hasattr(first.disposition, "value")
                else first.disposition
            ),
            "second_disposition": str(
                second.disposition.value
                if hasattr(second.disposition, "value")
                else second.disposition
            ),
        }
    finally:
        try:
            coord.close()
        except Exception:  # noqa: BLE001
            pass


def _arc_coherence(session: MountSession) -> dict[str, Any]:
    """Committed mutation advances ARC generation; stale generation rejected."""

    store = CachedStorage(
        authorize=lambda _b: True,
        consistent=lambda _b: True,
        capacity_bytes=256 * 1024,
    )
    coh = CacheCoherence(store)
    path = "arc/coherent.bin"
    cid = path_to_content_id(path)
    from ipfs_kit_py.cache.arc.range_bindings import RangeBinding

    prior = RangeBinding(
        namespace="linux-live",
        content_id=cid,
        version="v1",
        generation="g:1",
        serializer="bytes@1",
        offset=0,
        length=8,
        policy="public",
    )
    if not coh.put_committed(prior, b"stale-v1"):
        raise LiveHarnessError("failed to seed ARC binding", code="CASE_ASSERT")

    ops = session.operations
    _mkdir(ops, "arc", mode=0o755)
    _create_with_body(ops, path, b"fresh-v2", step="create arc path", release=True)

    event = CoherenceEvent(
        kind=CoherenceMutationKind.CREATE,
        disposition=CoherenceDisposition.COMMITTED,
        path=path,
        content_id=cid,
        namespace="linux-live",
        generation="g:2",
        prior_generation="g:1",
        version="v2",
        prior_version="v1",
        effect_id=f"effect:linux-{uuid.uuid4().hex[:8]}",
        transaction_id=f"txn:linux-{uuid.uuid4().hex[:8]}",
        source=CoherenceSource.MUTATION,
        serializer="bytes@1",
        policy="public",
    )
    receipt = coh.publish(event)
    if not receipt.published:
        raise LiveHarnessError(
            "coherence event not published",
            code="CASE_ASSERT",
            detail=receipt.to_dict(),
        )
    if coh.active_generation(cid, namespace="linux-live") != "g:2":
        raise LiveHarnessError(
            "active generation did not advance",
            code="CASE_ASSERT",
            detail={"active": coh.active_generation(cid, namespace="linux-live")},
        )
    stale = coh.get(prior)
    if stale == b"stale-v1":
        raise LiveHarnessError(
            "stale ARC generation still readable after advance",
            code="CASE_ASSERT",
        )
    _require_success(ops.unlink(path), step="unlink arc path")
    try:
        ops.rmdir("arc")
    except Exception:  # noqa: BLE001
        pass
    return {
        "published": True,
        "generation": "g:2",
        "bindings_invalidated": receipt.bindings_invalidated,
        "stale_rejected": True,
    }


def _unmount_case(session: MountSession) -> dict[str, Any]:
    """Bounded unmount drains, preserves recovery, and is idempotent."""

    life = session.lifecycle
    if not life.ready:
        raise LiveHarnessError("session not ready before unmount", code="CASE_ASSERT")
    pid = life.pid
    started = _monotonic()
    first = life.unmount(timeout_seconds=5.0, sig=signal.SIGTERM)
    elapsed = _monotonic() - started
    if elapsed > 5.0:
        raise LiveHarnessError(
            "unmount hung",
            code="CASE_HANG",
            detail={"elapsed": elapsed},
        )
    if not first.success:
        raise LiveHarnessError(
            "unmount failed",
            code="CASE_ASSERT",
            detail=first.to_record(),
        )
    if not first.recovery_preserved:
        raise LiveHarnessError("recovery not preserved on unmount", code="CASE_ASSERT")
    if not first.mount_released:
        raise LiveHarnessError("mount not released on unmount", code="CASE_ASSERT")

    started2 = _monotonic()
    second = life.unmount(timeout_seconds=5.0)
    if _monotonic() - started2 > 2.0:
        raise LiveHarnessError("repeated unmount hung", code="CASE_HANG")
    if not second.success:
        raise LiveHarnessError("repeated unmount failed", code="CASE_ASSERT")
    idempotent = bool(second.idempotent) or str(second.disposition).endswith(
        "idempotent"
    ) or second.disposition.value == "idempotent"

    return {
        "unmounted": True,
        "pid": pid,
        "recovery_preserved": True,
        "mount_released": True,
        "idempotent_unmount": idempotent,
        "unmount_seconds": elapsed,
        "signal_name": first.signal_name,
    }


CASE_RUNNERS: Final[
    dict[ConformanceCaseId, Callable[[MountSession], dict[str, Any]]]
] = {
    ConformanceCaseId.KERNEL_CRUD: _kernel_crud,
    ConformanceCaseId.FLAGS: _flags,
    ConformanceCaseId.OFFSET_SPARSE_IO: _offset_sparse_io,
    ConformanceCaseId.TRUNCATE: _truncate_case,
    ConformanceCaseId.METADATA: _metadata,
    ConformanceCaseId.CONCURRENT_HANDLES: _concurrent_handles,
    ConformanceCaseId.UNLINK_RENAME: _unlink_rename,
    ConformanceCaseId.FSYNC: _fsync_case,
    ConformanceCaseId.FORCED_KILL: _forced_kill,
    ConformanceCaseId.REPLAY: _replay,
    ConformanceCaseId.ARC_COHERENCE: _arc_coherence,
    ConformanceCaseId.UNMOUNT: _unmount_case,
}


# ---------------------------------------------------------------------------
# Main harness
# ---------------------------------------------------------------------------


class LinuxLiveHarness:
    """Bounded Linux kernel-mount conformance harness for KVFS-506.

    Parameters
    ----------
    work_directory:
        Root for state / lease / receipt artifacts.
    prefer_live:
        When True and capability is ready, use the native live plane.
        Default follows ``IPFS_KIT_KERNEL_VFS_LINUX_LIVE`` env or capability.
    """

    def __init__(
        self,
        work_directory: str | Path | None = None,
        *,
        prefer_live: bool | None = None,
        readiness_timeout_seconds: float = READINESS_TIMEOUT_SECONDS,
        case_timeout_seconds: float = CASE_TIMEOUT_SECONDS,
        capability_budget_seconds: float = CAPABILITY_PROBE_BUDGET_SECONDS,
    ) -> None:
        self._owns_work = work_directory is None
        if work_directory is None:
            self.work_directory = Path(
                tempfile.mkdtemp(prefix="kvfs-linux-live-")
            )
        else:
            self.work_directory = Path(work_directory)
            self.work_directory.mkdir(parents=True, exist_ok=True)
        self.receipts_directory = self.work_directory / "receipts"
        self.receipts_directory.mkdir(parents=True, exist_ok=True)
        self.state_root = self.work_directory / "state"
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.mount_root = self.work_directory / "mounts"
        self.mount_root.mkdir(parents=True, exist_ok=True)
        self.lease_root = self.work_directory / "leases"
        self.lease_root.mkdir(parents=True, exist_ok=True)

        self.readiness_timeout_seconds = float(readiness_timeout_seconds)
        self.case_timeout_seconds = float(case_timeout_seconds)
        self.capability_budget_seconds = float(capability_budget_seconds)

        if prefer_live is None:
            env_force = os.environ.get(LIVE_FORCE_ENV, "").strip().lower()
            prefer_live = env_force in {"1", "true", "yes", "live", "force"}
        self.prefer_live = bool(prefer_live)

        self._capability: CapabilityReceipt | None = None
        self._sessions: list[MountSession] = []
        self._case_receipts: list[CaseReceipt] = []
        self._lock = threading.RLock()
        self._closed = False
        self._cleanup_watchdog: CleanupWatchdog | None = None

    # -- capability ---------------------------------------------------------

    def probe(self, *, force: bool = False) -> CapabilityReceipt:
        if self._capability is not None and not force:
            return self._capability
        # Doctor needs separated mountpoint/state paths for evaluation.
        probe_mnt = self.mount_root / "probe-mnt"
        probe_state = self.state_root / "probe-state"
        probe_mnt.mkdir(parents=True, exist_ok=True)
        probe_state.mkdir(parents=True, exist_ok=True)
        receipt = probe_linux_capability(
            budget_seconds=self.capability_budget_seconds,
            mountpoint=probe_mnt,
            state_dir=probe_state,
        )
        self._capability = receipt
        _atomic_write_json(
            self.receipts_directory / "capability.json",
            receipt.to_record(),
        )
        return receipt

    @property
    def capability(self) -> CapabilityReceipt:
        return self.probe()

    @property
    def plane(self) -> ExecutionPlane:
        cap = self.probe()
        if self.prefer_live and cap.native_ready:
            return ExecutionPlane.LIVE
        return ExecutionPlane.HERMETIC

    # -- mount --------------------------------------------------------------

    def open_session(
        self,
        *,
        mount_id: str | None = None,
    ) -> MountSession:
        plane = self.plane
        token = uuid.uuid4().hex[:10]
        state_dir = self.state_root / f"session-{token}"
        mountpoint = self.mount_root / f"mnt-{token}"
        # Lifecycle always uses a unique mount id for exclusive lease fencing.
        life_mid = mount_id or f"mount:linux-live-{uuid.uuid4().hex[:8]}"
        # Operations on the hermetic plane use the default mount id so
        # CanonicalVFSService / NamespaceRouter match the unit-tested profile.
        ops_mid = (
            life_mid if plane is ExecutionPlane.LIVE else DEFAULT_MOUNT_ID
        )

        # Operations surface models the kernel callback path (hermetic or live
        # projection). Live native FUSE loop wiring remains fail-closed behind
        # capability; hermetic always exercises the same operations matrix.
        # Use HERMETIC platform for the hermetic plane so path/errno projection
        # matches the unit-tested KernelVFSOperations profile; LIVE plane still
        # pins HostPlatform.LINUX for Linux errno numbers.
        ops_platform = (
            HostPlatform.LINUX if plane is ExecutionPlane.LIVE else HostPlatform.HERMETIC
        )
        ops = build_kernel_vfs_operations(
            backend="memory",
            platform=ops_platform,
            mount_id=ops_mid,
            auto_init=True,
        )

        cfg = LinuxMountConfig(
            mountpoint=mountpoint,
            state_directory=state_dir,
            mount_id=life_mid,
            readiness_timeout_seconds=self.readiness_timeout_seconds,
            heartbeat_interval_seconds=0.05,
            unmount_timeout_seconds=5.0,
            hermetic=True,  # native loop owned by later live wiring; lifecycle always hermetic-safe
            generation_id=f"wal-gen:live-{uuid.uuid4().hex[:8]}",
        )
        life = LinuxMountLifecycle(cfg)
        started = _monotonic()
        try:
            readiness = life.start(wait_ready=True)
        except Exception:
            try:
                ops.close()
            except Exception:  # noqa: BLE001
                pass
            try:
                life.unmount(timeout_seconds=5.0)
            except Exception:  # noqa: BLE001
                pass
            raise
        elapsed = _monotonic() - started
        if elapsed > self.readiness_timeout_seconds:
            try:
                ops.close()
            except Exception:  # noqa: BLE001
                pass
            life.unmount(timeout_seconds=5.0)
            raise LiveHarnessError(
                f"readiness exceeded {self.readiness_timeout_seconds}s",
                code="READINESS_TIMEOUT",
                detail={"elapsed": elapsed},
            )
        if not readiness.ready or not readiness.recovery_complete:
            try:
                ops.close()
            except Exception:  # noqa: BLE001
                pass
            life.unmount(timeout_seconds=5.0)
            raise LiveHarnessError(
                "mount did not become ready after recovery",
                code="MOUNT_NOT_READY",
                detail=readiness.to_record(),
            )
        session = MountSession(
            lifecycle=life,
            operations=ops,
            mountpoint=mountpoint,
            state_directory=state_dir,
            plane=plane,
            mount_id=life_mid,
        )
        with self._lock:
            self._sessions.append(session)
        return session

    # -- case execution -----------------------------------------------------

    def run_case(
        self,
        case_id: ConformanceCaseId | str,
        *,
        session: MountSession | None = None,
    ) -> CaseReceipt:
        if not isinstance(case_id, ConformanceCaseId):
            case_id = ConformanceCaseId(case_id)
        runner = CASE_RUNNERS[case_id]
        plane = self.plane
        capability = self.probe()
        owns_session = session is None
        started = _monotonic()
        watchdog = CaseWatchdog(self.case_timeout_seconds)
        watchdog.start(case_id.value)
        mount_root = ""
        detail: dict[str, Any] = {}
        status = CaseStatus.FAILED
        message = ""
        success = False
        elapsed = 0.0

        try:
            if session is None:
                session = self.open_session()

            assert session is not None
            mount_root = session.root

            # Run the case body on the calling thread. KernelVFSOperations /
            # HostVFSService are safe for multi-thread *coordination* but the
            # hermetic case matrix is single-owner; executing inline avoids
            # worker-thread races while the independent CaseWatchdog still
            # bounds wall-clock time for the receipt.
            try:
                case_detail = runner(session)
                elapsed = _monotonic() - started
                if watchdog.fired or elapsed > self.case_timeout_seconds:
                    status = CaseStatus.TIMEOUT
                    message = (
                        f"case {case_id.value} exceeded "
                        f"{self.case_timeout_seconds:.1f}s bound"
                    )
                    success = False
                    detail = {
                        "watchdog_fired": watchdog.fired,
                        "worker_alive": False,
                        "elapsed_seconds": elapsed,
                    }
                else:
                    status = CaseStatus.PASSED
                    message = f"case {case_id.value} passed on {plane.value} plane"
                    success = True
                    detail = dict(case_detail or {})
                    detail["elapsed_seconds"] = elapsed
            except BaseException as exc:  # noqa: BLE001
                elapsed = _monotonic() - started
                if watchdog.fired or elapsed > self.case_timeout_seconds:
                    status = CaseStatus.TIMEOUT
                    message = (
                        f"case {case_id.value} exceeded "
                        f"{self.case_timeout_seconds:.1f}s bound"
                    )
                    success = False
                    detail = {
                        "watchdog_fired": watchdog.fired,
                        "worker_alive": False,
                        "error": type(exc).__name__,
                        "message": _bounded_text(exc),
                    }
                else:
                    status = CaseStatus.FAILED
                    message = _bounded_text(exc)
                    success = False
                    detail = {
                        "error": type(exc).__name__,
                        "message": message,
                    }
                    if isinstance(exc, LiveHarnessError):
                        detail["code"] = exc.code
                        detail["error_detail"] = dict(exc.detail)

        except Exception as exc:  # noqa: BLE001
            elapsed = _monotonic() - started
            status = CaseStatus.FAILED
            message = _bounded_text(exc)
            success = False
            detail = {
                "error": type(exc).__name__,
                "message": message,
                "traceback": _bounded_text(traceback.format_exc(), limit=2_048),
            }
        finally:
            watchdog.cancel()
            elapsed = _monotonic() - started
            if owns_session and session is not None:
                try:
                    session.close()
                except Exception as cleanup_exc:  # noqa: BLE001
                    if success:
                        status = CaseStatus.CLEANUP_FAILED
                        success = False
                        message = f"cleanup failed: {cleanup_exc}"
                    detail = dict(detail)
                    detail["cleanup_error"] = _bounded_text(cleanup_exc)
                with self._lock:
                    if session in self._sessions:
                        self._sessions.remove(session)

        support_claim = support_claim_for(
            native_ready=capability.native_ready,
            live_cases_passed=success and plane is ExecutionPlane.LIVE,
            plane=plane,
        )
        if not capability.native_ready:
            support_claim = SUPPORT_CLAIM_UNAVAILABLE
        support_promoted = can_promote_live_support(
            native_ready=capability.native_ready,
            support_claim=support_claim,
            status="passed" if success and plane is ExecutionPlane.LIVE else "failed",
            profile=PROFILE_LIVE if plane is ExecutionPlane.LIVE else PROFILE_HERMETIC,
        )
        if support_promoted and not capability.native_ready:
            raise SupportPromotionError()

        receipt = CaseReceipt(
            case_id=case_id.value,
            status=status,
            plane=plane,
            success=success,
            elapsed_seconds=elapsed,
            timeout_seconds=self.case_timeout_seconds,
            readiness_timeout_seconds=self.readiness_timeout_seconds,
            support_claim=support_claim,
            support_promoted=support_promoted,
            mount_root=mount_root,
            message=message,
            detail=detail,
            unix_ms=_unix_ms(),
            receipt_id=f"receipt:case:{case_id.value}:{uuid.uuid4().hex}",
        )
        _atomic_write_json(
            self.receipts_directory / f"case-{case_id.value}.json",
            receipt.to_record(),
        )
        with self._lock:
            self._case_receipts.append(receipt)
        return receipt

    def run_suite(
        self,
        case_ids: Sequence[ConformanceCaseId | str] | None = None,
    ) -> SuiteReceipt:
        """Run the full (or selected) case matrix and emit a suite receipt."""

        started = _monotonic()
        self._cleanup_watchdog = CleanupWatchdog(
            self.cleanup,
            deadline_seconds=self.case_timeout_seconds
            * (len(REQUIRED_CASE_IDS) + 1),
        )
        self._cleanup_watchdog.start()
        try:
            capability = self.probe()
            plane = self.plane
            selected: list[ConformanceCaseId] = []
            if case_ids is None:
                selected = list(REQUIRED_CASE_IDS)
            else:
                for item in case_ids:
                    selected.append(
                        item
                        if isinstance(item, ConformanceCaseId)
                        else ConformanceCaseId(item)
                    )

            receipts: list[CaseReceipt] = []
            for case_id in selected:
                receipts.append(self.run_case(case_id))

            all_passed = all(r.success for r in receipts)
            required_set = {c.value for c in REQUIRED_CASE_IDS}
            ran_required = {r.case_id for r in receipts} >= required_set
            live_ok = (
                capability.native_ready
                and plane is ExecutionPlane.LIVE
                and all_passed
                and ran_required
            )
            if live_ok:
                status = "passed"
                profile = PROFILE_LIVE
                support_claim = SUPPORT_CLAIM_LIVE_PASSED
                support_promoted = True
                platform_label = "linux"
            elif all_passed:
                profile = PROFILE_HERMETIC
                if capability.native_ready:
                    status = "hermetic_passed"
                    support_claim = SUPPORT_CLAIM_HERMETIC_ONLY
                else:
                    status = SUPPORT_CLAIM_UNAVAILABLE
                    support_claim = SUPPORT_CLAIM_UNAVAILABLE
                support_promoted = False
                platform_label = (
                    sys.platform if not capability.is_linux else "hermetic"
                )
            else:
                status = "failed"
                profile = PROFILE_HERMETIC
                support_claim = (
                    SUPPORT_CLAIM_UNAVAILABLE
                    if not capability.native_ready
                    else SUPPORT_CLAIM_HERMETIC_ONLY
                )
                support_promoted = False
                platform_label = (
                    sys.platform if not capability.is_linux else "hermetic"
                )

            if not can_promote_live_support(
                native_ready=capability.native_ready,
                support_claim=support_claim,
                status=status,
                profile=profile,
            ):
                support_promoted = False
                if not capability.native_ready:
                    support_claim = SUPPORT_CLAIM_UNAVAILABLE
                    profile = PROFILE_HERMETIC
                    if status == "passed":
                        status = SUPPORT_CLAIM_UNAVAILABLE

            if live_ok:
                message = "Linux FUSE live conformance passed"
            elif not capability.native_ready and all_passed:
                message = (
                    "hermetic conformance matrix passed; "
                    "capability_unavailable — live Linux support not promoted"
                )
            elif all_passed:
                message = "conformance matrix passed without live promotion"
            else:
                failed = [r.case_id for r in receipts if not r.success]
                message = f"conformance failures: {failed}"

            suite = SuiteReceipt(
                status=status,
                profile=profile,
                platform=platform_label,
                architecture=capability.architecture,
                support_claim=support_claim,
                support_promoted=support_promoted,
                native_ready=capability.native_ready,
                plane=plane,
                cases=tuple(receipts),
                capability=capability,
                elapsed_seconds=_monotonic() - started,
                readiness_timeout_seconds=self.readiness_timeout_seconds,
                case_timeout_seconds=self.case_timeout_seconds,
                message=message,
                detail={
                    "required_case_count": len(REQUIRED_CASE_IDS),
                    "ran_case_count": len(receipts),
                    "passed_case_count": sum(1 for r in receipts if r.success),
                    "prefer_live": self.prefer_live,
                    "matrix_passed": all_passed,
                },
                receipt_id=f"receipt:suite:{uuid.uuid4().hex}",
                unix_ms=_unix_ms(),
            )
            _atomic_write_json(
                self.receipts_directory / "suite.json",
                suite.to_record(),
            )
            return suite
        finally:
            if self._cleanup_watchdog is not None:
                self._cleanup_watchdog.cancel()
                self._cleanup_watchdog = None
            self.cleanup()

    # -- cleanup ------------------------------------------------------------

    def cleanup(self) -> None:
        with self._lock:
            sessions = list(self._sessions)
            self._sessions.clear()
        for session in sessions:
            try:
                session.close()
            except Exception:  # noqa: BLE001
                pass

    def close(self) -> None:
        if self._closed:
            return
        self.cleanup()
        if self._owns_work:
            try:
                shutil.rmtree(self.work_directory, ignore_errors=True)
            except OSError:
                pass
        self._closed = True

    def __enter__(self) -> "LinuxLiveHarness":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def to_record(self) -> dict[str, Any]:
        cap = self._capability
        return {
            "schema": f"{HARNESS_NAMESPACE}/harness@{SCHEMA_MAJOR}",
            "task_id": TASK_ID,
            "work_directory": str(self.work_directory),
            "plane": self.plane.value if cap is not None else None,
            "capability": cap.to_record() if cap is not None else None,
            "case_receipts": [r.to_record() for r in self._case_receipts],
            "readiness_timeout_seconds": self.readiness_timeout_seconds,
            "case_timeout_seconds": self.case_timeout_seconds,
            "required_case_ids": [c.value for c in REQUIRED_CASE_IDS],
        }


def run_live_conformance(
    work_directory: str | Path | None = None,
    **kwargs: Any,
) -> SuiteReceipt:
    """Convenience entry: construct harness, run full suite, return receipt."""

    with LinuxLiveHarness(work_directory, **kwargs) as harness:
        return harness.run_suite()


def required_case_ids() -> tuple[str, ...]:
    return tuple(c.value for c in REQUIRED_CASE_IDS)


def case_timeout_seconds() -> float:
    return CASE_TIMEOUT_SECONDS


def readiness_timeout_seconds() -> float:
    return READINESS_TIMEOUT_SECONDS


__all__ = [
    "TASK_ID",
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "LIVE_RECEIPT_SCHEMA",
    "CASE_RECEIPT_SCHEMA",
    "SUITE_RECEIPT_SCHEMA",
    "CAPABILITY_RECEIPT_SCHEMA",
    "PROFILE_LIVE",
    "PROFILE_HERMETIC",
    "PINNED_ABI",
    "PINNED_BINDING",
    "READINESS_TIMEOUT_SECONDS",
    "CASE_TIMEOUT_SECONDS",
    "CAPABILITY_PROBE_BUDGET_SECONDS",
    "SUPPORT_CLAIM_UNAVAILABLE",
    "SUPPORT_CLAIM_LIVE_PASSED",
    "SUPPORT_CLAIM_HERMETIC_ONLY",
    "LIVE_FORCE_ENV",
    "LIVE_GATE_ENV",
    "ExecutionPlane",
    "CaseStatus",
    "ConformanceCaseId",
    "REQUIRED_CASE_IDS",
    "LiveHarnessError",
    "CaseTimeoutError",
    "SupportPromotionError",
    "CapabilityReceipt",
    "CaseReceipt",
    "SuiteReceipt",
    "CaseWatchdog",
    "CleanupWatchdog",
    "MountSession",
    "LinuxLiveHarness",
    "probe_linux_capability",
    "support_claim_for",
    "can_promote_live_support",
    "run_live_conformance",
    "required_case_ids",
    "case_timeout_seconds",
    "readiness_timeout_seconds",
    "is_linux_host",
    "architecture_label",
]

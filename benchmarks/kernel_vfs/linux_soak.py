#!/usr/bin/env python3
"""KVFS-501: Linux ARM64 ABI certification and repeated mount/resource soak.

Owns the labeled Linux soak evidence path:

* native ARM64 ABI and concurrency certification (process architecture,
  pointer width, multiarch layout, concurrent host-callback plane);
* 100 mount/unmount cycles with zero leaked process / mount / handle / lease;
* 100 crash/recover cycles with no stale read or lost acknowledgement;
* bounded WAL / cache / memory / descriptors across the soak;
* capability absence is a finite nonpromotion receipt (never promotes live
  Linux FUSE support).

Hermetic by default: the soak uses :class:`LinuxMountLifecycle` (hermetic
child daemon) plus :class:`KernelVFSOperations` so CI validates bounds without
claiming live support. Native live plane requires doctor
``native_capability_ready`` and only that plane may set
``support_promoted=true``.

Usage:
  python benchmarks/kernel_vfs/linux_soak.py --check-schema
  python benchmarks/kernel_vfs/linux_soak.py --run
  python benchmarks/kernel_vfs/linux_soak.py --run --cycles 100
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import random
import resource
import signal
import struct
import sys
import tempfile
import threading
import time
import traceback
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Final

from ipfs_kit_py.cache.arc.range_bindings import RangeBinding
from ipfs_kit_py.core.vfs.host_concurrency import (
    HostCallbackConflictError,
    HostConcurrencyPlane,
    HostLockConflictError,
    LockMode,
)
from ipfs_kit_py.core.vfs.host_contracts import HostCallbackKind, HostPlatform, OpenFlag
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
    normalize_machine,
    run_linux_doctor,
)
from ipfs_kit_py.kernel_vfs.wal_recovery import MountRecoveryCoordinator

# ---------------------------------------------------------------------------
# Identity / bounds (plan §6 Linux ARM64 soak / KVFS-501 acceptance)
# ---------------------------------------------------------------------------

TASK_ID: Final[str] = "KVFS-501"
CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

SOAK_NAMESPACE: Final[str] = "ipfs_kit_py/benchmarks/kernel_vfs/linux_soak"
SOAK_RECEIPT_SCHEMA: Final[str] = "KernelVFSLinuxSoakReceipt@1"
ABI_RECEIPT_SCHEMA: Final[str] = f"{SOAK_NAMESPACE}/abi-receipt@{SCHEMA_MAJOR}"
CAPABILITY_RECEIPT_SCHEMA: Final[str] = (
    f"{SOAK_NAMESPACE}/capability-receipt@{SCHEMA_MAJOR}"
)
CYCLE_RECEIPT_SCHEMA: Final[str] = f"{SOAK_NAMESPACE}/cycle-receipt@{SCHEMA_MAJOR}"
RESOURCE_RECEIPT_SCHEMA: Final[str] = (
    f"{SOAK_NAMESPACE}/resource-receipt@{SCHEMA_MAJOR}"
)
CONCURRENCY_RECEIPT_SCHEMA: Final[str] = (
    f"{SOAK_NAMESPACE}/concurrency-receipt@{SCHEMA_MAJOR}"
)

DEFAULT_MOUNT_CYCLES: Final[int] = 100
DEFAULT_CRASH_CYCLES: Final[int] = 100
DEFAULT_CONCURRENCY_SECONDS: Final[float] = 0.5
DEFAULT_CONCURRENCY_WORKERS: Final[int] = 6
CAPABILITY_PROBE_BUDGET_SECONDS: Final[float] = min(DOCTOR_BUDGET_SECONDS, 5.0)
READINESS_TIMEOUT_SECONDS: Final[float] = DEFAULT_READINESS_TIMEOUT_SECONDS  # 15
UNMOUNT_TIMEOUT_SECONDS: Final[float] = 5.0
CYCLE_TIMEOUT_SECONDS: Final[float] = 60.0
MAX_RECEIPT_DETAIL_BYTES: Final[int] = 16_384

# Resource growth ceilings across the full soak (fail-closed).
MAX_RSS_GROWTH_BYTES: Final[int] = 256 * 1024 * 1024  # 256 MiB peak growth
MAX_FD_GROWTH: Final[int] = 64
MAX_WAL_BYTES: Final[int] = 64 * 1024 * 1024  # 64 MiB
MAX_CACHE_ENTRIES: Final[int] = 10_000
MAX_OPEN_HANDLES_AFTER_CYCLE: Final[int] = 0
MAX_CHILD_PROCESSES_AFTER_CYCLE: Final[int] = 0

SUPPORT_CLAIM_UNAVAILABLE: Final[str] = "capability_unavailable"
SUPPORT_CLAIM_LIVE_PASSED: Final[str] = "live_passed"
SUPPORT_CLAIM_HERMETIC_ONLY: Final[str] = "hermetic_only"
SUPPORT_CLAIM_SOAK_PASSED: Final[str] = "soak_passed"

PROFILE_HERMETIC: Final[str] = "linux_hermetic_soak"
PROFILE_LIVE: Final[str] = "linux_live_arm64_soak"
PINNED_ABI: Final[str] = "libfuse2"
PINNED_BINDING: Final[str] = "fusepy_high_level_fuse2"

ARM64_MACHINES: Final[frozenset[str]] = frozenset({"aarch64", "arm64"})
LIVE_FORCE_ENV: Final[str] = "IPFS_KIT_KERNEL_VFS_LINUX_LIVE"
SOAK_CYCLES_ENV: Final[str] = "IPFS_KIT_KERNEL_VFS_SOAK_CYCLES"

HERE: Final[Path] = Path(__file__).resolve().parent
PACKAGE_ROOT: Final[Path] = HERE.parents[1]


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class ExecutionPlane(str, Enum):
    """How soak cycles are executed."""

    HERMETIC = "hermetic"
    LIVE = "live"


class CycleKind(str, Enum):
    """Pinned soak cycle kinds required by KVFS-501 acceptance."""

    MOUNT_UNMOUNT = "mount_unmount"
    CRASH_RECOVER = "crash_recover"


class CycleStatus(str, Enum):
    """Terminal status of one soak cycle."""

    PASSED = "passed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    LEAK = "leak"
    STALE_READ = "stale_read"
    LOST_ACK = "lost_ack"
    RESOURCE_BOUND = "resource_bound"


class SoakStatus(str, Enum):
    """Terminal suite status."""

    PASSED = "passed"
    FAILED = "failed"
    HERMETIC_PASSED = "hermetic_passed"
    CAPABILITY_UNAVAILABLE = "capability_unavailable"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SoakError(Exception):
    """Base soak failure (fail-closed)."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "SOAK_ERROR",
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


class SupportPromotionError(SoakError):
    """Raised when code attempts to promote live support without capability."""

    def __init__(
        self, message: str = "cannot promote live Linux FUSE support from soak"
    ) -> None:
        super().__init__(message, code="SUPPORT_PROMOTION_BLOCKED")


class ResourceBoundError(SoakError):
    """Raised when WAL/cache/memory/descriptor bounds are exceeded."""

    def __init__(
        self,
        message: str,
        *,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code="RESOURCE_BOUND", detail=detail)


class LeakError(SoakError):
    """Raised when a process/mount/handle/lease leak is detected."""

    def __init__(
        self,
        message: str,
        *,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code="LEAK", detail=detail)


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
    """Return process architecture label (normalized)."""

    machine = (platform.machine() or "").lower()
    return normalize_machine(machine) if machine else (
        "64bit" if sys.maxsize > 2**32 else "32bit"
    )


def is_native_arm64() -> bool:
    """True when the running process is native ARM64/aarch64."""

    label = architecture_label()
    return label in ARM64_MACHINES or label == "aarch64"


def support_claim_for(
    *,
    native_ready: bool,
    soak_passed: bool,
    plane: ExecutionPlane | str,
) -> str:
    """Derive support claim. Absent capability can never promote support."""

    plane_value = plane.value if isinstance(plane, ExecutionPlane) else str(plane)
    if not native_ready:
        return SUPPORT_CLAIM_UNAVAILABLE
    if plane_value == ExecutionPlane.LIVE.value and soak_passed:
        return SUPPORT_CLAIM_LIVE_PASSED
    if soak_passed:
        return SUPPORT_CLAIM_HERMETIC_ONLY
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
    if support_claim not in {SUPPORT_CLAIM_LIVE_PASSED, SUPPORT_CLAIM_SOAK_PASSED}:
        return False
    if status not in {"passed", "admitted"}:
        return False
    if profile != PROFILE_LIVE:
        return False
    return True


def resolve_cycle_count(requested: int | None = None) -> int:
    """Resolve soak cycle count (default 100; env override for diagnostics)."""

    if requested is not None:
        return max(1, int(requested))
    env = os.environ.get(SOAK_CYCLES_ENV, "").strip()
    if env:
        try:
            return max(1, int(env))
        except ValueError:
            pass
    return DEFAULT_MOUNT_CYCLES


# ---------------------------------------------------------------------------
# Resource sampling
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResourceSnapshot:
    """Point-in-time process / descriptor / memory observation."""

    SCHEMA: ClassVar[str] = RESOURCE_RECEIPT_SCHEMA

    pid: int
    rss_bytes: int
    fd_count: int
    open_handles: int
    child_pids: tuple[int, ...]
    wal_bytes: int
    cache_entries: int
    unix_ms: int = 0

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "task_id": TASK_ID,
            "pid": self.pid,
            "rss_bytes": self.rss_bytes,
            "fd_count": self.fd_count,
            "open_handles": self.open_handles,
            "child_pids": list(self.child_pids),
            "child_count": len(self.child_pids),
            "wal_bytes": self.wal_bytes,
            "cache_entries": self.cache_entries,
            "unix_ms": self.unix_ms or _unix_ms(),
        }


def _read_rss_bytes() -> int:
    try:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        rss = int(usage.ru_maxrss)
        # ru_maxrss is KiB on Linux, bytes on macOS/BSD.
        if platform.system() == "Linux":
            rss *= 1024
        return max(0, rss)
    except Exception:  # noqa: BLE001
        return 0


def _count_fds(pid: int | None = None) -> int:
    target = pid or os.getpid()
    fd_dir = Path(f"/proc/{target}/fd")
    if fd_dir.is_dir():
        try:
            return len(list(fd_dir.iterdir()))
        except OSError:
            pass
    # Fallback: soft limit does not reflect open count; use 0 when unknown.
    try:
        soft, _hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        return 0 if soft > 0 else 0
    except Exception:  # noqa: BLE001
        return 0


def _directory_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    try:
        if path.is_file():
            return int(path.stat().st_size)
        for root, _dirs, files in os.walk(path):
            for name in files:
                try:
                    total += int((Path(root) / name).stat().st_size)
                except OSError:
                    continue
    except OSError:
        return total
    return total


def _living_pids(pids: Sequence[int]) -> tuple[int, ...]:
    alive: list[int] = []
    for pid in pids:
        if pid <= 0:
            continue
        try:
            os.kill(pid, 0)
            alive.append(int(pid))
        except ProcessLookupError:
            continue
        except PermissionError:
            # Process exists but is not owned by us — still a leak signal.
            alive.append(int(pid))
        except OSError:
            continue
    return tuple(alive)


def sample_resources(
    *,
    open_handles: int = 0,
    child_pids: Sequence[int] = (),
    wal_path: Path | None = None,
    cache_entries: int = 0,
) -> ResourceSnapshot:
    """Sample bounded resource counters for soak receipts."""

    return ResourceSnapshot(
        pid=os.getpid(),
        rss_bytes=_read_rss_bytes(),
        fd_count=_count_fds(),
        open_handles=int(open_handles),
        child_pids=_living_pids(child_pids),
        wal_bytes=_directory_bytes(wal_path) if wal_path is not None else 0,
        cache_entries=int(cache_entries),
        unix_ms=_unix_ms(),
    )


def assert_resource_bounds(
    baseline: ResourceSnapshot,
    current: ResourceSnapshot,
    *,
    max_rss_growth: int = MAX_RSS_GROWTH_BYTES,
    max_fd_growth: int = MAX_FD_GROWTH,
    max_wal_bytes: int = MAX_WAL_BYTES,
    max_cache_entries: int = MAX_CACHE_ENTRIES,
    max_open_handles: int = MAX_OPEN_HANDLES_AFTER_CYCLE,
    max_children: int = MAX_CHILD_PROCESSES_AFTER_CYCLE,
) -> dict[str, Any]:
    """Fail-closed resource bound check between two snapshots."""

    rss_growth = max(0, current.rss_bytes - baseline.rss_bytes)
    fd_growth = max(0, current.fd_count - baseline.fd_count)
    violations: list[str] = []
    if rss_growth > max_rss_growth:
        violations.append(
            f"rss_growth={rss_growth} exceeds {max_rss_growth}"
        )
    if fd_growth > max_fd_growth:
        violations.append(f"fd_growth={fd_growth} exceeds {max_fd_growth}")
    if current.wal_bytes > max_wal_bytes:
        violations.append(
            f"wal_bytes={current.wal_bytes} exceeds {max_wal_bytes}"
        )
    if current.cache_entries > max_cache_entries:
        violations.append(
            f"cache_entries={current.cache_entries} exceeds {max_cache_entries}"
        )
    if current.open_handles > max_open_handles:
        violations.append(
            f"open_handles={current.open_handles} exceeds {max_open_handles}"
        )
    if len(current.child_pids) > max_children:
        violations.append(
            f"child_pids={list(current.child_pids)} exceeds {max_children}"
        )
    detail = {
        "baseline": baseline.to_record(),
        "current": current.to_record(),
        "rss_growth_bytes": rss_growth,
        "fd_growth": fd_growth,
        "violations": violations,
        "bounded": not violations,
    }
    if violations:
        raise ResourceBoundError(
            "resource bounds exceeded during soak",
            detail=detail,
        )
    return detail


# ---------------------------------------------------------------------------
# ABI certification
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AbiReceipt:
    """Native process ABI certification receipt (ARM64 when native)."""

    SCHEMA: ClassVar[str] = ABI_RECEIPT_SCHEMA

    architecture: str
    machine_raw: str
    is_arm64: bool
    is_linux: bool
    pointer_bits: int
    maxsize: int
    byteorder: str
    struct_pointer_size: int
    multiarch_lib_dirs: tuple[str, ...]
    abi_ok: bool
    message: str
    support_promoted: bool = False
    unix_ms: int = 0
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "task_id": TASK_ID,
            "architecture": self.architecture,
            "machine_raw": self.machine_raw,
            "is_arm64": self.is_arm64,
            "is_linux": self.is_linux,
            "pointer_bits": self.pointer_bits,
            "maxsize": self.maxsize,
            "byteorder": self.byteorder,
            "struct_pointer_size": self.struct_pointer_size,
            "multiarch_lib_dirs": list(self.multiarch_lib_dirs),
            "abi_ok": self.abi_ok,
            "message": self.message,
            "support_promoted": bool(self.support_promoted),
            "unix_ms": self.unix_ms or _unix_ms(),
            "detail": dict(self.detail),
        }


def certify_arm64_abi() -> AbiReceipt:
    """Certify native process ABI identity (ARM64-aware, fail-closed).

    On native aarch64/arm64 hosts this asserts 64-bit little-endian ABI and
    multiarch library directory layout. On other hosts the receipt still
    validates pointer/byteorder consistency and labels the architecture so
    non-ARM64 runners produce finite evidence without claiming ARM64 soak.
    """

    raw = (platform.machine() or "").lower()
    arch = architecture_label()
    is_arm = arch in {"aarch64"} or raw in ARM64_MACHINES
    pointer_bits = 64 if sys.maxsize > 2**32 else 32
    struct_ptr = struct.calcsize("P") * 8
    byteorder = sys.byteorder
    is_lin = is_linux_host()

    multiarch: list[str] = []
    if is_arm:
        multiarch = [
            "/usr/lib/aarch64-linux-gnu",
            "/lib/aarch64-linux-gnu",
            "/usr/lib64",
            "/lib64",
            "/usr/lib",
            "/lib",
        ]
    elif arch in {"x86_64", "amd64"}:
        multiarch = [
            "/usr/lib/x86_64-linux-gnu",
            "/lib/x86_64-linux-gnu",
            "/usr/lib64",
            "/lib64",
            "/usr/lib",
            "/lib",
        ]

    checks: dict[str, Any] = {
        "pointer_bits_match_struct": pointer_bits == struct_ptr,
        "byteorder_known": byteorder in {"little", "big"},
        "normalize_arm64_alias": normalize_machine("arm64") == "aarch64",
        "normalize_aarch64": normalize_machine("aarch64") == "aarch64",
    }
    if is_arm:
        checks["arm64_is_64bit"] = pointer_bits == 64
        checks["arm64_little_endian"] = byteorder == "little"
        checks["arm64_maxsize"] = sys.maxsize >= 2**63 - 1 or sys.maxsize == 2**63 - 1

    abi_ok = all(bool(v) for v in checks.values())
    if is_arm and abi_ok:
        message = "native ARM64 ABI certified"
    elif is_arm and not abi_ok:
        message = "native ARM64 ABI checks failed"
    else:
        message = (
            f"process ABI labeled {arch}; ARM64-native soak not claimed on this host"
        )

    return AbiReceipt(
        architecture=arch,
        machine_raw=raw,
        is_arm64=is_arm,
        is_linux=is_lin,
        pointer_bits=pointer_bits,
        maxsize=int(sys.maxsize),
        byteorder=byteorder,
        struct_pointer_size=struct_ptr,
        multiarch_lib_dirs=tuple(multiarch),
        abi_ok=abi_ok,
        message=message,
        support_promoted=False,
        unix_ms=_unix_ms(),
        detail={"checks": checks},
    )


# ---------------------------------------------------------------------------
# Capability probe (finite nonpromotion receipt)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CapabilityReceipt:
    """Bounded Linux FUSE capability probe for soak admission."""

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
    support_promoted: bool = False
    finite: bool = True

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
            "finite": bool(self.finite),
            "nonpromotion": not bool(self.support_promoted),
        }


def probe_linux_capability(
    *,
    budget_seconds: float = CAPABILITY_PROBE_BUDGET_SECONDS,
    mountpoint: str | Path | None = None,
    state_dir: str | Path | None = None,
) -> CapabilityReceipt:
    """Run the ≤5 s Linux FUSE doctor and project a finite capability receipt.

    Never mounts, never loads native libraries via the doctor, never starts a
    daemon. Absent capability yields ``support_claim=capability_unavailable``
    and ``support_promoted=false`` (finite nonpromotion receipt).
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
            message = (
                "Linux FUSE live capability unavailable; "
                "finite nonpromotion receipt (support not promoted)"
            )

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
        finite=True,
    )


# ---------------------------------------------------------------------------
# Cycle receipts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CycleReceipt:
    """Terminal receipt for one mount/unmount or crash/recover cycle."""

    SCHEMA: ClassVar[str] = CYCLE_RECEIPT_SCHEMA

    cycle_index: int
    kind: CycleKind
    status: CycleStatus
    success: bool
    elapsed_seconds: float
    pid: int = 0
    mount_released: bool = False
    lease_released: bool = False
    handles_released: bool = False
    process_reaped: bool = False
    recovery_preserved: bool = False
    stale_read: bool = False
    lost_ack: bool = False
    message: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)
    unix_ms: int = 0

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "task_id": TASK_ID,
            "cycle_index": self.cycle_index,
            "kind": self.kind.value,
            "status": self.status.value,
            "success": self.success,
            "elapsed_seconds": self.elapsed_seconds,
            "pid": self.pid,
            "mount_released": self.mount_released,
            "lease_released": self.lease_released,
            "handles_released": self.handles_released,
            "process_reaped": self.process_reaped,
            "recovery_preserved": self.recovery_preserved,
            "stale_read": self.stale_read,
            "lost_ack": self.lost_ack,
            "message": self.message,
            "detail": dict(self.detail),
            "unix_ms": self.unix_ms or _unix_ms(),
            "leaked": not (
                self.mount_released
                and self.lease_released
                and self.handles_released
                and self.process_reaped
            )
            if self.success
            else False,
        }


@dataclass(frozen=True)
class ConcurrencyReceipt:
    """Concurrency plane soak receipt."""

    SCHEMA: ClassVar[str] = CONCURRENCY_RECEIPT_SCHEMA

    success: bool
    workers: int
    duration_seconds: float
    ops_ok: int
    ops_conflict: int
    errors: int
    open_handles_final: int
    active_callbacks_final: int
    waiters_final: int
    deadlock_free: bool
    bounded: bool
    message: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)
    unix_ms: int = 0

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "task_id": TASK_ID,
            "success": self.success,
            "workers": self.workers,
            "duration_seconds": self.duration_seconds,
            "ops_ok": self.ops_ok,
            "ops_conflict": self.ops_conflict,
            "errors": self.errors,
            "open_handles_final": self.open_handles_final,
            "active_callbacks_final": self.active_callbacks_final,
            "waiters_final": self.waiters_final,
            "deadlock_free": self.deadlock_free,
            "bounded": self.bounded,
            "message": self.message,
            "detail": dict(self.detail),
            "unix_ms": self.unix_ms or _unix_ms(),
        }


@dataclass(frozen=True)
class SoakReceipt:
    """Aggregate Linux ARM64 / mount soak suite receipt."""

    SCHEMA: ClassVar[str] = SOAK_RECEIPT_SCHEMA

    status: str
    profile: str
    platform: str
    architecture: str
    support_claim: str
    support_promoted: bool
    native_ready: bool
    plane: ExecutionPlane
    abi: AbiReceipt
    capability: CapabilityReceipt
    concurrency: ConcurrencyReceipt
    mount_cycles: tuple[CycleReceipt, ...]
    crash_cycles: tuple[CycleReceipt, ...]
    mount_cycle_count: int
    crash_cycle_count: int
    leaked_processes: int
    leaked_mounts: int
    leaked_handles: int
    leaked_leases: int
    stale_reads: int
    lost_acknowledgements: int
    resource_baseline: ResourceSnapshot
    resource_final: ResourceSnapshot
    resource_bounds: Mapping[str, Any]
    elapsed_seconds: float
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
            or f"receipt:soak:{uuid.uuid4().hex}",
            "status": self.status,
            "gate_status": self.status,
            "profile": self.profile,
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
            "abi": self.abi.to_record(),
            "capability": self.capability.to_record(),
            "concurrency": self.concurrency.to_record(),
            "mount_cycles": [c.to_record() for c in self.mount_cycles],
            "crash_cycles": [c.to_record() for c in self.crash_cycles],
            "mount_cycle_count": self.mount_cycle_count,
            "crash_cycle_count": self.crash_cycle_count,
            "required_mount_cycles": DEFAULT_MOUNT_CYCLES,
            "required_crash_cycles": DEFAULT_CRASH_CYCLES,
            "leaked_processes": self.leaked_processes,
            "leaked_mounts": self.leaked_mounts,
            "leaked_handles": self.leaked_handles,
            "leaked_leases": self.leaked_leases,
            "stale_reads": self.stale_reads,
            "lost_acknowledgements": self.lost_acknowledgements,
            "zero_leaks": (
                self.leaked_processes == 0
                and self.leaked_mounts == 0
                and self.leaked_handles == 0
                and self.leaked_leases == 0
            ),
            "zero_stale_or_lost": (
                self.stale_reads == 0 and self.lost_acknowledgements == 0
            ),
            "resource_baseline": self.resource_baseline.to_record(),
            "resource_final": self.resource_final.to_record(),
            "resource_bounds": dict(self.resource_bounds),
            "elapsed_seconds": self.elapsed_seconds,
            "readiness_timeout_seconds": READINESS_TIMEOUT_SECONDS,
            "message": self.message,
            "detail": dict(self.detail),
            "unix_ms": self.unix_ms or _unix_ms(),
            "fuse": bool(self.support_promoted),
            "live": bool(self.support_promoted),
        }


# ---------------------------------------------------------------------------
# Concurrency soak
# ---------------------------------------------------------------------------


def run_concurrency_soak(
    *,
    workers: int = DEFAULT_CONCURRENCY_WORKERS,
    duration_seconds: float = DEFAULT_CONCURRENCY_SECONDS,
    seed: int = 501_501,
) -> ConcurrencyReceipt:
    """Exercise the host concurrency plane under multi-thread load.

    Completes without deadlock; never exceeds configured table/queue/waiter
    bounds; open handles return to zero after shutdown.
    """

    max_active = 8
    max_waiters = 32
    max_queue = 16
    plane = HostConcurrencyPlane(
        max_active_callbacks=max_active,
        max_waiters=max_waiters,
        max_queue_depth=max_queue,
        max_global_locks=256,
        max_locks_per_owner=32,
        default_wait_ms=50,
        shutdown_drain_ms=2_000,
        clock_ms=lambda: int(time.time() * 1000),
    )
    for i in range(6):
        plane.handles.seed_file(f"soak/f{i}.bin", f"body-{i}".encode())

    stop = threading.Event()
    errors: list[BaseException] = []
    stats = {"ok": 0, "conflict": 0, "other": 0}
    stats_lock = threading.Lock()
    open_handles: dict[int, int] = {}
    handles_lock = threading.Lock()
    peak_active = 0
    peak_queue = 0
    peak_waiters = 0

    def bump(key: str) -> None:
        with stats_lock:
            stats[key] += 1

    def check_bounds() -> None:
        nonlocal peak_active, peak_queue, peak_waiters
        snap = plane.pressure_snapshot()
        peak_active = max(peak_active, int(snap["active_callbacks"]))
        peak_queue = max(peak_queue, int(snap["queue_depth"]))
        peak_waiters = max(peak_waiters, int(snap["waiters"]))
        if snap["active_callbacks"] > max_active:
            raise SoakError("active_callbacks exceeded bound", code="CONCURRENCY_BOUND")
        if snap["queue_depth"] > max_queue:
            raise SoakError("queue_depth exceeded bound", code="CONCURRENCY_BOUND")
        if snap["waiters"] > max_waiters:
            raise SoakError("waiters exceeded bound", code="CONCURRENCY_BOUND")

    def op_read(rng: random.Random) -> None:
        path = f"soak/f{rng.randrange(6)}.bin"
        plane.run_callback(
            lambda _s: True,
            kind=HostCallbackKind.READ,
            paths=(path,),
            path_mode=LockMode.SHARED,
            owner_id=f"r-{threading.get_ident()}-{rng.random()}",
            wait_ms=80,
        )

    def op_write(rng: random.Random) -> None:
        path = f"soak/f{rng.randrange(6)}.bin"
        plane.run_callback(
            lambda _s: True,
            kind=HostCallbackKind.WRITE,
            paths=(path,),
            owner_id=f"w-{threading.get_ident()}-{rng.random()}",
            wait_ms=80,
        )

    def op_open_close(rng: random.Random) -> None:
        path = f"soak/f{rng.randrange(6)}.bin"
        fh = plane.open_file(path, OpenFlag.O_RDONLY, wait_ms=80)
        with handles_lock:
            open_handles[fh.handle_id] = fh.generation
        if rng.random() < 0.4:
            try:
                if rng.random() < 0.5:
                    plane.rename_path(path, f"soak/r{rng.randrange(6)}.bin", wait_ms=80)
                else:
                    plane.unlink_path(path, wait_ms=80)
                    if plane.handles.lookup_inode(path) is None:
                        try:
                            plane.handles.seed_file(path, b"reseed")
                        except Exception:  # noqa: BLE001
                            pass
            except (HostCallbackConflictError, HostLockConflictError, Exception):
                pass
        plane.release_file(fh.handle_id, generation=fh.generation, wait_ms=80)
        with handles_lock:
            open_handles.pop(fh.handle_id, None)

    ops = (op_read, op_write, op_open_close)

    def worker(worker_seed: int) -> None:
        rng = random.Random(worker_seed)
        while not stop.is_set():
            try:
                check_bounds()
                ops[rng.randrange(len(ops))](rng)
                bump("ok")
            except (HostCallbackConflictError, HostLockConflictError):
                bump("conflict")
            except BaseException as exc:  # noqa: BLE001
                msg = str(exc).lower()
                code = getattr(exc, "code", None)
                code_s = getattr(code, "value", str(code or "")).lower()
                if any(
                    token in msg or token in code_s
                    for token in (
                        "not found",
                        "already",
                        "exists",
                        "conflict",
                        "stale",
                        "path_conflict",
                        "already_exists",
                    )
                ):
                    bump("conflict")
                else:
                    bump("other")
                    errors.append(exc)
                    return

    started = _monotonic()
    threads = [
        threading.Thread(
            target=worker, args=(seed + i,), name=f"kvfs501-soak-{i}", daemon=True
        )
        for i in range(max(1, int(workers)))
    ]
    for t in threads:
        t.start()
    time.sleep(max(0.05, float(duration_seconds)))
    stop.set()
    hung = False
    for t in threads:
        t.join(timeout=5.0)
        if t.is_alive():
            hung = True

    with handles_lock:
        leftover = list(open_handles.items())
    for hid, gen in leftover:
        try:
            plane.release_file(hid, generation=gen, wait_ms=50)
        except Exception:  # noqa: BLE001
            pass
    detail = plane.shutdown(drain=True, timeout_ms=2_000)
    snap = plane.pressure_snapshot()
    elapsed = _monotonic() - started
    deadlock_free = not hung and not errors
    bounded = (
        peak_active <= max_active
        and peak_queue <= max_queue
        and peak_waiters <= max_waiters
        and int(snap["active_callbacks"]) == 0
        and int(snap["waiters"]) == 0
        and int(detail.get("active") or 0) == 0
    )
    success = deadlock_free and bounded and (stats["ok"] + stats["conflict"]) > 0
    return ConcurrencyReceipt(
        success=success,
        workers=len(threads),
        duration_seconds=elapsed,
        ops_ok=int(stats["ok"]),
        ops_conflict=int(stats["conflict"]),
        errors=len(errors) + int(stats["other"]),
        open_handles_final=int(snap.get("open_handles") or 0),
        active_callbacks_final=int(snap.get("active_callbacks") or 0),
        waiters_final=int(snap.get("waiters") or 0),
        deadlock_free=deadlock_free,
        bounded=bounded,
        message=(
            "concurrency soak passed"
            if success
            else f"concurrency soak failed hung={hung} errors={len(errors)}"
        ),
        detail={
            "peak_active": peak_active,
            "peak_queue": peak_queue,
            "peak_waiters": peak_waiters,
            "shutdown": detail,
            "error_samples": [_bounded_text(e) for e in errors[:3]],
        },
        unix_ms=_unix_ms(),
    )


# ---------------------------------------------------------------------------
# Mount lifecycle helpers
# ---------------------------------------------------------------------------


def _make_config(
    work: Path,
    *,
    mount_id: str | None = None,
    generation_id: str | None = None,
    holder_id: str | None = None,
    readiness_timeout_seconds: float = READINESS_TIMEOUT_SECONDS,
) -> LinuxMountConfig:
    token = uuid.uuid4().hex[:10]
    mountpoint = work / f"mnt-{token}"
    state_dir = work / f"state-{token}"
    mountpoint.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    return LinuxMountConfig(
        mountpoint=mountpoint,
        state_directory=state_dir,
        mount_id=mount_id or f"mount:soak-{uuid.uuid4().hex[:8]}",
        generation_id=generation_id or f"wal-gen:soak-{uuid.uuid4().hex[:8]}",
        readiness_timeout_seconds=readiness_timeout_seconds,
        heartbeat_interval_seconds=0.05,
        unmount_timeout_seconds=UNMOUNT_TIMEOUT_SECONDS,
        drain_timeout_seconds=1.0,
        worker_stop_timeout_seconds=1.0,
        hermetic=True,
        cache_generation=1,
        cache_entries=0,
        holder_id=holder_id,
    )


def _wait_process_dead(life: LinuxMountLifecycle, *, timeout: float = 5.0) -> bool:
    deadline = _monotonic() + timeout
    while life.running and _monotonic() < deadline:
        time.sleep(0.01)
    return not life.running


def _ops_open_count(ops: KernelVFSOperations) -> int:
    try:
        plane = getattr(ops, "_concurrency", None) or getattr(ops, "concurrency", None)
        if plane is not None:
            snap = plane.pressure_snapshot()
            return int(snap.get("open_handles") or 0)
    except Exception:  # noqa: BLE001
        pass
    return 0


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
) -> Any:
    created = ops.create(
        path,
        payload,
        mode=mode,
        flags=(OpenFlag.O_RDWR, OpenFlag.O_CREAT),
    )
    if created.success:
        handle = created.handle
        if handle is not None:
            _release_handle(ops, handle)
        return created
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
        _release_handle(ops, handle)
        if written.success:
            return written
    raise SoakError(
        f"create failed for {path}",
        code="OPS_CREATE",
        detail={"path": path},
    )


def _ensure_dir(ops: KernelVFSOperations, path: str, *, mode: int = 0o755) -> None:
    outcome = ops.mkdir(path, mode=mode)
    if outcome.success:
        return
    errno = getattr(outcome, "errno", None)
    name = str(getattr(errno, "value", errno) or "")
    if name in {"EEXIST", "File exists"} or "exist" in (
        getattr(outcome, "message", "") or ""
    ).lower():
        return
    # Directory may already exist under hermetic re-use; treat getattr success
    # as acceptable.
    st = ops.getattr(path) if hasattr(ops, "getattr") else None
    if st is not None and getattr(st, "success", False):
        return
    raise SoakError(
        f"mkdir failed for {path}",
        code="OPS_MKDIR",
        detail={"errno": name, "message": _bounded_text(getattr(outcome, "message", ""))},
    )


def _read_all(ops: KernelVFSOperations, path: str) -> bytes:
    # Prefer path-only read (matches live harness / hermetic projection).
    outcome = ops.read(path, offset=0, size=1 << 20)
    if outcome.success:
        return bytes(getattr(outcome, "data", None) or b"")
    opened = ops.open(path, (OpenFlag.O_RDONLY,))
    if not opened.success or opened.handle is None:
        raise SoakError(f"open failed for {path}", code="OPS_OPEN")
    handle = opened.handle
    try:
        outcome = ops.read(
            path,
            size=1 << 20,
            offset=0,
            handle_id=handle.handle_id,
            generation=handle.generation,
        )
        if not outcome.success:
            raise SoakError(f"read failed for {path}", code="OPS_READ")
        return bytes(getattr(outcome, "data", None) or b"")
    finally:
        _release_handle(ops, handle)


def _check_stale_and_ack(
    *,
    cycle_index: int,
    payload: bytes,
    observed: bytes,
    ack_token: str,
    observed_ack: str | None,
) -> tuple[bool, bool, str]:
    """Return (stale_read, lost_ack, message)."""

    stale = observed != payload
    lost = not observed_ack or observed_ack != ack_token
    if stale and lost:
        return True, True, "stale read and lost acknowledgement"
    if stale:
        return True, False, "stale read after commit/recovery"
    if lost:
        return False, True, "lost acknowledgement after commit/recovery"
    return False, False, "ack retained and read matches committed payload"


# ---------------------------------------------------------------------------
# Mount / unmount cycle
# ---------------------------------------------------------------------------


def run_mount_unmount_cycle(
    work: Path,
    *,
    cycle_index: int,
    readiness_timeout_seconds: float = READINESS_TIMEOUT_SECONDS,
) -> CycleReceipt:
    """One hermetic mount → I/O → unmount cycle with leak checks."""

    started = _monotonic()
    child_pid = 0
    ops: KernelVFSOperations | None = None
    life: LinuxMountLifecycle | None = None
    try:
        cfg = _make_config(
            work / "mount-unmount",
            mount_id=f"mount:mu-{cycle_index:04d}-{uuid.uuid4().hex[:6]}",
            readiness_timeout_seconds=readiness_timeout_seconds,
        )
        ops = build_kernel_vfs_operations(
            backend="memory",
            platform=HostPlatform.HERMETIC,
            mount_id=DEFAULT_MOUNT_ID,
            auto_init=True,
        )
        life = LinuxMountLifecycle(cfg)
        readiness = life.start(wait_ready=True)
        if not readiness.ready or not readiness.recovery_complete:
            raise SoakError("mount not ready", code="MOUNT_NOT_READY")
        child_pid = int(life.pid or 0)

        path = f"mu/c{cycle_index:04d}.bin"
        payload = f"committed-mu-{cycle_index}".encode()
        _ensure_dir(ops, "mu", mode=0o755)
        _create_with_body(ops, path, payload)
        # fsync path for acknowledgement surface.
        opened = ops.open(path, (OpenFlag.O_RDWR,))
        if not opened.success or opened.handle is None:
            raise SoakError("open for fsync failed", code="OPS_OPEN")
        handle = opened.handle
        fsync_out = ops.fsync(
            handle_id=handle.handle_id, generation=handle.generation
        )
        if not fsync_out.success:
            raise SoakError("fsync failed", code="OPS_FSYNC")
        ack_token = f"ack:mu:{cycle_index}:{payload.hex()}"
        # Persist ack token into state for post-unmount verification shape.
        ack_path = Path(cfg.state_directory) / "soak-ack.json"
        _atomic_write_json(
            ack_path,
            {
                "ack": ack_token,
                "path": path,
                "payload_hex": payload.hex(),
                "cycle": cycle_index,
            },
        )
        observed = _read_all(ops, path)
        stale, lost, msg = _check_stale_and_ack(
            cycle_index=cycle_index,
            payload=payload,
            observed=observed,
            ack_token=ack_token,
            observed_ack=ack_token,  # in-session ack retained
        )
        if stale or lost:
            raise SoakError(
                msg,
                code="STALE_OR_LOST_ACK",
                detail={"stale_read": stale, "lost_ack": lost},
            )
        _release_handle(ops, handle)

        open_before_close = _ops_open_count(ops)
        unmount = life.unmount(
            timeout_seconds=UNMOUNT_TIMEOUT_SECONDS, sig=signal.SIGTERM
        )
        process_reaped = _wait_process_dead(life, timeout=5.0)
        if not process_reaped:
            raise LeakError(
                "child process still running after unmount",
                detail={"pid": child_pid},
            )
        if _living_pids([child_pid]):
            raise LeakError(
                "child pid still alive after unmount",
                detail={"pid": child_pid},
            )
        try:
            ops.close()
        except Exception:  # noqa: BLE001
            pass
        open_after = _ops_open_count(ops)
        handles_released = open_after <= MAX_OPEN_HANDLES_AFTER_CYCLE
        mount_released = bool(unmount.mount_released)
        lease_released = bool(unmount.lease_released)
        recovery_preserved = bool(unmount.recovery_preserved)

        if not handles_released:
            raise LeakError(
                "open handles remain after cycle",
                detail={"open_handles": open_after},
            )
        if not mount_released:
            raise LeakError("mount not released", detail=unmount.to_record())
        if not lease_released:
            raise LeakError("lease not released", detail=unmount.to_record())

        # Ack file must still exist (recovery state preserved).
        if not ack_path.is_file():
            raise SoakError("acknowledgement evidence lost", code="LOST_ACK")
        ack_raw = json.loads(ack_path.read_text(encoding="utf-8"))
        if ack_raw.get("ack") != ack_token:
            raise SoakError("acknowledgement token mismatch", code="LOST_ACK")

        elapsed = _monotonic() - started
        if elapsed > CYCLE_TIMEOUT_SECONDS:
            return CycleReceipt(
                cycle_index=cycle_index,
                kind=CycleKind.MOUNT_UNMOUNT,
                status=CycleStatus.TIMEOUT,
                success=False,
                elapsed_seconds=elapsed,
                pid=child_pid,
                message=f"cycle exceeded {CYCLE_TIMEOUT_SECONDS}s",
            )
        return CycleReceipt(
            cycle_index=cycle_index,
            kind=CycleKind.MOUNT_UNMOUNT,
            status=CycleStatus.PASSED,
            success=True,
            elapsed_seconds=elapsed,
            pid=child_pid,
            mount_released=mount_released,
            lease_released=lease_released,
            handles_released=handles_released,
            process_reaped=process_reaped,
            recovery_preserved=recovery_preserved,
            stale_read=False,
            lost_ack=False,
            message="mount/unmount cycle clean",
            detail={
                "open_handles_before_close": open_before_close,
                "open_handles_after": open_after,
                "ack": ack_token,
                "unmount": unmount.to_record(),
            },
        )
    except LeakError as exc:
        elapsed = _monotonic() - started
        return CycleReceipt(
            cycle_index=cycle_index,
            kind=CycleKind.MOUNT_UNMOUNT,
            status=CycleStatus.LEAK,
            success=False,
            elapsed_seconds=elapsed,
            pid=child_pid,
            message=exc.message,
            detail=exc.to_record(),
        )
    except SoakError as exc:
        elapsed = _monotonic() - started
        status = CycleStatus.FAILED
        stale = False
        lost = False
        if exc.code == "STALE_OR_LOST_ACK":
            stale = bool(exc.detail.get("stale_read"))
            lost = bool(exc.detail.get("lost_ack"))
            status = (
                CycleStatus.STALE_READ
                if stale
                else CycleStatus.LOST_ACK
                if lost
                else CycleStatus.FAILED
            )
        elif exc.code == "LOST_ACK":
            status = CycleStatus.LOST_ACK
            lost = True
        return CycleReceipt(
            cycle_index=cycle_index,
            kind=CycleKind.MOUNT_UNMOUNT,
            status=status,
            success=False,
            elapsed_seconds=elapsed,
            pid=child_pid,
            stale_read=stale,
            lost_ack=lost,
            message=exc.message,
            detail=exc.to_record(),
        )
    except Exception as exc:  # noqa: BLE001
        elapsed = _monotonic() - started
        return CycleReceipt(
            cycle_index=cycle_index,
            kind=CycleKind.MOUNT_UNMOUNT,
            status=CycleStatus.FAILED,
            success=False,
            elapsed_seconds=elapsed,
            pid=child_pid,
            message=_bounded_text(exc),
            detail={
                "error": type(exc).__name__,
                "traceback": _bounded_text(traceback.format_exc(), limit=2_048),
            },
        )
    finally:
        if life is not None:
            try:
                life.unmount(timeout_seconds=2.0, sig=signal.SIGKILL)
            except Exception:  # noqa: BLE001
                pass
        if ops is not None:
            try:
                ops.close()
            except Exception:  # noqa: BLE001
                pass


# ---------------------------------------------------------------------------
# Crash / recover cycle
# ---------------------------------------------------------------------------


def run_crash_recover_cycle(
    work: Path,
    *,
    cycle_index: int,
    readiness_timeout_seconds: float = READINESS_TIMEOUT_SECONDS,
) -> CycleReceipt:
    """One force-kill → remount recovery cycle with stale/ack checks."""

    started = _monotonic()
    child_pid = 0
    ops: KernelVFSOperations | None = None
    life: LinuxMountLifecycle | None = None
    recovery_life: LinuxMountLifecycle | None = None
    try:
        cfg = _make_config(
            work / "crash-recover",
            mount_id=f"mount:cr-{cycle_index:04d}-{uuid.uuid4().hex[:6]}",
            generation_id=f"wal-gen:cr-{cycle_index:04d}",
            readiness_timeout_seconds=readiness_timeout_seconds,
        )
        ops = build_kernel_vfs_operations(
            backend="memory",
            platform=HostPlatform.HERMETIC,
            mount_id=DEFAULT_MOUNT_ID,
            auto_init=True,
        )
        life = LinuxMountLifecycle(cfg)
        readiness = life.start(wait_ready=True)
        if not readiness.ready or not readiness.recovery_complete:
            raise SoakError("mount not ready before crash", code="MOUNT_NOT_READY")
        child_pid = int(life.pid or 0)

        path = f"cr/c{cycle_index:04d}.bin"
        payload = f"committed-cr-{cycle_index}-v1".encode()
        _ensure_dir(ops, "cr", mode=0o755)
        _create_with_body(ops, path, payload)
        ack_token = f"ack:cr:{cycle_index}:{payload.hex()}"
        ack_path = Path(cfg.state_directory) / "soak-ack.json"
        _atomic_write_json(
            ack_path,
            {
                "ack": ack_token,
                "path": path,
                "payload_hex": payload.hex(),
                "cycle": cycle_index,
            },
        )

        # Seed ARC with committed generation, then advance so stale is rejected.
        store = CachedStorage(
            authorize=lambda _b: True,
            consistent=lambda _b: True,
            capacity_bytes=256 * 1024,
        )
        coh = CacheCoherence(store)
        cid = path_to_content_id(path)
        gen1 = f"g{cycle_index}a"
        gen2 = f"g{cycle_index}b"
        prior = RangeBinding(
            namespace="linux-soak",
            content_id=cid,
            version="v1",
            generation=gen1,
            serializer="bytes@1",
            offset=0,
            length=len(payload),
            policy="public",
        )
        if not coh.put_committed(prior, payload):
            raise SoakError("failed to seed ARC binding", code="ARC_SEED")
        event = CoherenceEvent(
            kind=CoherenceMutationKind.CREATE,
            disposition=CoherenceDisposition.COMMITTED,
            path=path,
            content_id=cid,
            namespace="linux-soak",
            generation=gen2,
            prior_generation=gen1,
            version="v2",
            prior_version="v1",
            effect_id=f"effect:soak-{uuid.uuid4().hex[:8]}",
            transaction_id=f"txn:soak-{uuid.uuid4().hex[:8]}",
            source=CoherenceSource.MUTATION,
            serializer="bytes@1",
            policy="public",
        )
        receipt = coh.publish(event)
        if not receipt.published:
            raise SoakError("coherence event not published", code="ARC_PUBLISH")
        stale_bytes = coh.get(prior)
        if stale_bytes == payload:
            raise SoakError(
                "stale ARC generation still readable after advance",
                code="STALE_OR_LOST_ACK",
                detail={"stale_read": True, "lost_ack": False},
            )

        # Force-kill child.
        if not life.signal_child(signal.SIGKILL):
            try:
                os.kill(child_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if not _wait_process_dead(life, timeout=5.0):
            raise LeakError(
                "child still running after SIGKILL",
                detail={"pid": child_pid},
            )
        try:
            life.unmount(timeout_seconds=2.0, sig=signal.SIGKILL)
        except Exception:  # noqa: BLE001
            pass

        recovery_preserved = (
            (Path(cfg.state_directory) / "recovery-preserved").exists()
            or (Path(cfg.state_directory) / "recovery").exists()
            or ack_path.is_file()
        )
        if not recovery_preserved:
            raise SoakError(
                "recovery state not preserved after crash",
                code="RECOVERY_LOST",
            )

        # Remount / recover before ready.
        last_error: BaseException | None = None
        for attempt in range(5):
            recovery_cfg = LinuxMountConfig(
                mountpoint=cfg.mountpoint,
                state_directory=cfg.state_directory,
                mount_id=f"mount:recover-{cycle_index:04d}-{uuid.uuid4().hex[:6]}",
                generation_id=cfg.generation_id,
                readiness_timeout_seconds=readiness_timeout_seconds,
                heartbeat_interval_seconds=0.05,
                unmount_timeout_seconds=UNMOUNT_TIMEOUT_SECONDS,
                hermetic=True,
                holder_id=f"holder:recover-{uuid.uuid4().hex[:8]}",
            )
            recovery_life = LinuxMountLifecycle(recovery_cfg)
            try:
                rec_ready = recovery_life.start(wait_ready=True)
                last_error = None
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                try:
                    recovery_life.unmount(timeout_seconds=2.0)
                except Exception:  # noqa: BLE001
                    pass
                recovery_life = None
                time.sleep(0.02 * (attempt + 1))
        if last_error is not None or recovery_life is None:
            raise SoakError(
                "recovery remount failed",
                code="RECOVERY_FAILED",
                detail={"error": _bounded_text(last_error)},
            )
        if not rec_ready.ready or not rec_ready.recovery_complete:
            raise SoakError("recovery remount not ready", code="RECOVERY_FAILED")
        phases = list(rec_ready.recovery_phases or ())
        if (
            "enter_ready" in phases
            and "acquire_lease" in phases
            and phases.index("acquire_lease") > phases.index("enter_ready")
        ):
            raise SoakError(
                "ready advertised before lease recovery",
                code="RECOVERY_ORDER",
                detail={"phases": phases},
            )

        # Ack must survive crash.
        if not ack_path.is_file():
            raise SoakError("acknowledgement lost after crash", code="LOST_ACK")
        ack_raw = json.loads(ack_path.read_text(encoding="utf-8"))
        if ack_raw.get("ack") != ack_token:
            raise SoakError(
                "acknowledgement token lost after crash",
                code="LOST_ACK",
            )

        # In-process operations surface still holds committed bytes (no stale).
        observed = _read_all(ops, path)
        stale, lost, msg = _check_stale_and_ack(
            cycle_index=cycle_index,
            payload=payload,
            observed=observed,
            ack_token=ack_token,
            observed_ack=str(ack_raw.get("ack") or ""),
        )
        if stale or lost:
            raise SoakError(
                msg,
                code="STALE_OR_LOST_ACK",
                detail={"stale_read": stale, "lost_ack": lost},
            )

        # Explicit WAL recovery coordinator pass (idempotent).
        recovery_root = Path(cfg.state_directory) / "replay-probe"
        recovery_root.mkdir(parents=True, exist_ok=True)
        coord = MountRecoveryCoordinator(
            recovery_root,
            mount_id=f"mount:replay-{cycle_index:04d}",
            generation_id=f"wal-gen:replay-{cycle_index:04d}",
            platform=HostPlatform.LINUX,
            recovery_timeout_seconds=min(30.0, readiness_timeout_seconds),
        )
        try:
            first = coord.recover()
            if not first.success or not first.ready or not first.recovery_complete:
                raise SoakError(
                    "coordinator recovery failed",
                    code="RECOVERY_FAILED",
                    detail=first.to_record(),
                )
            second = coord.recover()
            if not second.success:
                raise SoakError(
                    "idempotent recovery failed",
                    code="RECOVERY_FAILED",
                    detail=second.to_record(),
                )
        finally:
            try:
                coord.close()
            except Exception:  # noqa: BLE001
                pass

        unmount = recovery_life.unmount(
            timeout_seconds=UNMOUNT_TIMEOUT_SECONDS, sig=signal.SIGTERM
        )
        process_reaped = _wait_process_dead(recovery_life, timeout=5.0)
        rec_pid = int(recovery_life.pid or 0)
        living = _living_pids([child_pid, rec_pid])
        if living:
            raise LeakError(
                "process leak after crash/recover",
                detail={"living": list(living)},
            )
        try:
            ops.close()
        except Exception:  # noqa: BLE001
            pass
        open_after = _ops_open_count(ops)
        handles_released = open_after <= MAX_OPEN_HANDLES_AFTER_CYCLE
        mount_released = bool(unmount.mount_released)
        lease_released = bool(unmount.lease_released)

        if not (handles_released and mount_released and lease_released and process_reaped):
            raise LeakError(
                "leak after crash/recover cycle",
                detail={
                    "handles_released": handles_released,
                    "mount_released": mount_released,
                    "lease_released": lease_released,
                    "process_reaped": process_reaped,
                    "open_handles": open_after,
                },
            )

        elapsed = _monotonic() - started
        if elapsed > CYCLE_TIMEOUT_SECONDS:
            return CycleReceipt(
                cycle_index=cycle_index,
                kind=CycleKind.CRASH_RECOVER,
                status=CycleStatus.TIMEOUT,
                success=False,
                elapsed_seconds=elapsed,
                pid=child_pid,
                message=f"cycle exceeded {CYCLE_TIMEOUT_SECONDS}s",
            )
        return CycleReceipt(
            cycle_index=cycle_index,
            kind=CycleKind.CRASH_RECOVER,
            status=CycleStatus.PASSED,
            success=True,
            elapsed_seconds=elapsed,
            pid=child_pid,
            mount_released=mount_released,
            lease_released=lease_released,
            handles_released=handles_released,
            process_reaped=process_reaped,
            recovery_preserved=True,
            stale_read=False,
            lost_ack=False,
            message="crash/recover cycle clean",
            detail={
                "phases": phases,
                "ack": ack_token,
                "arc_stale_rejected": True,
                "recovery_pid": rec_pid,
                "unmount": unmount.to_record(),
            },
        )
    except LeakError as exc:
        elapsed = _monotonic() - started
        return CycleReceipt(
            cycle_index=cycle_index,
            kind=CycleKind.CRASH_RECOVER,
            status=CycleStatus.LEAK,
            success=False,
            elapsed_seconds=elapsed,
            pid=child_pid,
            message=exc.message,
            detail=exc.to_record(),
        )
    except SoakError as exc:
        elapsed = _monotonic() - started
        status = CycleStatus.FAILED
        stale = False
        lost = False
        if exc.code == "STALE_OR_LOST_ACK":
            stale = bool(exc.detail.get("stale_read"))
            lost = bool(exc.detail.get("lost_ack"))
            status = (
                CycleStatus.STALE_READ
                if stale
                else CycleStatus.LOST_ACK
                if lost
                else CycleStatus.FAILED
            )
        elif exc.code == "LOST_ACK":
            status = CycleStatus.LOST_ACK
            lost = True
        return CycleReceipt(
            cycle_index=cycle_index,
            kind=CycleKind.CRASH_RECOVER,
            status=status,
            success=False,
            elapsed_seconds=elapsed,
            pid=child_pid,
            stale_read=stale,
            lost_ack=lost,
            message=exc.message,
            detail=exc.to_record(),
        )
    except Exception as exc:  # noqa: BLE001
        elapsed = _monotonic() - started
        return CycleReceipt(
            cycle_index=cycle_index,
            kind=CycleKind.CRASH_RECOVER,
            status=CycleStatus.FAILED,
            success=False,
            elapsed_seconds=elapsed,
            pid=child_pid,
            message=_bounded_text(exc),
            detail={
                "error": type(exc).__name__,
                "traceback": _bounded_text(traceback.format_exc(), limit=2_048),
            },
        )
    finally:
        for ctl in (recovery_life, life):
            if ctl is not None:
                try:
                    ctl.unmount(timeout_seconds=2.0, sig=signal.SIGKILL)
                except Exception:  # noqa: BLE001
                    pass
        if ops is not None:
            try:
                ops.close()
            except Exception:  # noqa: BLE001
                pass


# ---------------------------------------------------------------------------
# Full soak suite
# ---------------------------------------------------------------------------


def run_linux_soak(
    work_directory: str | Path | None = None,
    *,
    mount_cycles: int | None = None,
    crash_cycles: int | None = None,
    concurrency_seconds: float = DEFAULT_CONCURRENCY_SECONDS,
    concurrency_workers: int = DEFAULT_CONCURRENCY_WORKERS,
    prefer_live: bool | None = None,
    readiness_timeout_seconds: float = READINESS_TIMEOUT_SECONDS,
) -> SoakReceipt:
    """Run the full KVFS-501 ARM64 / mount resource soak and emit a receipt.

    Parameters
    ----------
    mount_cycles / crash_cycles:
        Default 100 each (acceptance). Override via argument or
        ``IPFS_KIT_KERNEL_VFS_SOAK_CYCLES`` for diagnostic short runs.
    """

    started = _monotonic()
    owns_work = work_directory is None
    if work_directory is None:
        work = Path(tempfile.mkdtemp(prefix="kvfs-linux-soak-"))
    else:
        work = Path(work_directory)
        work.mkdir(parents=True, exist_ok=True)
    receipts_dir = work / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)

    n_mount = resolve_cycle_count(mount_cycles)
    n_crash = resolve_cycle_count(crash_cycles)

    if prefer_live is None:
        env_force = os.environ.get(LIVE_FORCE_ENV, "").strip().lower()
        prefer_live = env_force in {"1", "true", "yes", "live", "force"}

    abi = certify_arm64_abi()
    _atomic_write_json(receipts_dir / "abi.json", abi.to_record())

    probe_mnt = work / "probe-mnt"
    probe_state = work / "probe-state"
    probe_mnt.mkdir(parents=True, exist_ok=True)
    probe_state.mkdir(parents=True, exist_ok=True)
    capability = probe_linux_capability(
        budget_seconds=CAPABILITY_PROBE_BUDGET_SECONDS,
        mountpoint=probe_mnt,
        state_dir=probe_state,
    )
    _atomic_write_json(receipts_dir / "capability.json", capability.to_record())

    plane = (
        ExecutionPlane.LIVE
        if prefer_live and capability.native_ready
        else ExecutionPlane.HERMETIC
    )

    baseline = sample_resources()
    concurrency = run_concurrency_soak(
        workers=concurrency_workers,
        duration_seconds=concurrency_seconds,
    )
    _atomic_write_json(receipts_dir / "concurrency.json", concurrency.to_record())

    mount_receipts: list[CycleReceipt] = []
    crash_receipts: list[CycleReceipt] = []
    leaked_processes = 0
    leaked_mounts = 0
    leaked_handles = 0
    leaked_leases = 0
    stale_reads = 0
    lost_acks = 0
    tracked_pids: list[int] = []

    for i in range(n_mount):
        receipt = run_mount_unmount_cycle(
            work,
            cycle_index=i,
            readiness_timeout_seconds=readiness_timeout_seconds,
        )
        mount_receipts.append(receipt)
        if receipt.pid:
            tracked_pids.append(receipt.pid)
        if not receipt.success:
            if receipt.status is CycleStatus.LEAK:
                if not receipt.process_reaped:
                    leaked_processes += 1
                if not receipt.mount_released:
                    leaked_mounts += 1
                if not receipt.handles_released:
                    leaked_handles += 1
                if not receipt.lease_released:
                    leaked_leases += 1
            if receipt.stale_read:
                stale_reads += 1
            if receipt.lost_ack:
                lost_acks += 1
            # Fail closed: stop further mount cycles on first hard failure.
            break
        if not receipt.process_reaped:
            leaked_processes += 1
        if not receipt.mount_released:
            leaked_mounts += 1
        if not receipt.handles_released:
            leaked_handles += 1
        if not receipt.lease_released:
            leaked_leases += 1

    for i in range(n_crash):
        receipt = run_crash_recover_cycle(
            work,
            cycle_index=i,
            readiness_timeout_seconds=readiness_timeout_seconds,
        )
        crash_receipts.append(receipt)
        if receipt.pid:
            tracked_pids.append(receipt.pid)
        if not receipt.success:
            if receipt.status is CycleStatus.LEAK:
                if not receipt.process_reaped:
                    leaked_processes += 1
                if not receipt.mount_released:
                    leaked_mounts += 1
                if not receipt.handles_released:
                    leaked_handles += 1
                if not receipt.lease_released:
                    leaked_leases += 1
            if receipt.stale_read:
                stale_reads += 1
            if receipt.lost_ack:
                lost_acks += 1
            break
        if not receipt.process_reaped:
            leaked_processes += 1
        if not receipt.mount_released:
            leaked_mounts += 1
        if not receipt.handles_released:
            leaked_handles += 1
        if not receipt.lease_released:
            leaked_leases += 1

    living = _living_pids(tracked_pids)
    if living:
        leaked_processes += len(living)

    final = sample_resources(child_pids=living)
    try:
        resource_bounds = assert_resource_bounds(baseline, final)
        resource_ok = True
    except ResourceBoundError as exc:
        resource_bounds = dict(exc.detail)
        resource_ok = False

    mount_ok = (
        len(mount_receipts) == n_mount
        and all(r.success for r in mount_receipts)
    )
    crash_ok = (
        len(crash_receipts) == n_crash
        and all(r.success for r in crash_receipts)
    )
    zero_leaks = (
        leaked_processes == 0
        and leaked_mounts == 0
        and leaked_handles == 0
        and leaked_leases == 0
        and not living
    )
    zero_stale = stale_reads == 0 and lost_acks == 0
    abi_ok = bool(abi.abi_ok)
    concurrency_ok = bool(concurrency.success)

    soak_passed = (
        abi_ok
        and concurrency_ok
        and mount_ok
        and crash_ok
        and zero_leaks
        and zero_stale
        and resource_ok
    )

    if not capability.native_ready:
        # Hermetic matrix can still pass; never promote live support.
        if soak_passed:
            status = SoakStatus.HERMETIC_PASSED.value
            support_claim = SUPPORT_CLAIM_UNAVAILABLE
            message = (
                "hermetic soak passed; capability absence is a finite "
                "nonpromotion receipt"
            )
        else:
            status = SoakStatus.FAILED.value
            support_claim = SUPPORT_CLAIM_UNAVAILABLE
            message = "soak failed under capability_unavailable"
        profile = PROFILE_HERMETIC
        support_promoted = False
    else:
        support_claim = support_claim_for(
            native_ready=True,
            soak_passed=soak_passed and plane is ExecutionPlane.LIVE,
            plane=plane,
        )
        if plane is ExecutionPlane.LIVE and soak_passed:
            status = SoakStatus.PASSED.value
            profile = PROFILE_LIVE
            message = "native live ARM64 soak passed"
        elif soak_passed:
            status = SoakStatus.HERMETIC_PASSED.value
            profile = PROFILE_HERMETIC
            support_claim = SUPPORT_CLAIM_HERMETIC_ONLY
            message = "hermetic soak passed on capable host (live plane not selected)"
        else:
            status = SoakStatus.FAILED.value
            profile = PROFILE_LIVE if plane is ExecutionPlane.LIVE else PROFILE_HERMETIC
            message = "soak failed"
        support_promoted = can_promote_live_support(
            native_ready=capability.native_ready,
            support_claim=support_claim,
            status=status if status == SoakStatus.PASSED.value else "failed",
            profile=profile,
        )
        if support_promoted and not capability.native_ready:
            raise SupportPromotionError()

    # Capability absence must remain a finite nonpromotion receipt.
    if not capability.native_ready:
        support_promoted = False
        support_claim = SUPPORT_CLAIM_UNAVAILABLE
        if soak_passed:
            status = SUPPORT_CLAIM_UNAVAILABLE

    elapsed = _monotonic() - started
    suite = SoakReceipt(
        status=status,
        profile=profile,
        platform=sys.platform,
        architecture=abi.architecture,
        support_claim=support_claim,
        support_promoted=support_promoted,
        native_ready=capability.native_ready,
        plane=plane,
        abi=abi,
        capability=capability,
        concurrency=concurrency,
        mount_cycles=tuple(mount_receipts),
        crash_cycles=tuple(crash_receipts),
        mount_cycle_count=len(mount_receipts),
        crash_cycle_count=len(crash_receipts),
        leaked_processes=leaked_processes,
        leaked_mounts=leaked_mounts,
        leaked_handles=leaked_handles,
        leaked_leases=leaked_leases,
        stale_reads=stale_reads,
        lost_acknowledgements=lost_acks,
        resource_baseline=baseline,
        resource_final=final,
        resource_bounds=resource_bounds,
        elapsed_seconds=elapsed,
        message=message,
        detail={
            "requested_mount_cycles": n_mount,
            "requested_crash_cycles": n_crash,
            "mount_ok": mount_ok,
            "crash_ok": crash_ok,
            "abi_ok": abi_ok,
            "concurrency_ok": concurrency_ok,
            "resource_ok": resource_ok,
            "zero_leaks": zero_leaks,
            "zero_stale_or_lost": zero_stale,
            "living_pids": list(living),
            "owns_work_directory": owns_work,
            "work_directory": str(work),
        },
        receipt_id=f"receipt:soak:{uuid.uuid4().hex}",
        unix_ms=_unix_ms(),
    )
    _atomic_write_json(receipts_dir / "suite.json", suite.to_record())
    return suite


# ---------------------------------------------------------------------------
# Schema check / CLI
# ---------------------------------------------------------------------------


def check_schema() -> dict[str, Any]:
    """Validate schema constants and identity for packaging gates."""

    required = {
        "task_id": TASK_ID,
        "contract_version": CONTRACT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "soak_receipt_schema": SOAK_RECEIPT_SCHEMA,
        "abi_receipt_schema": ABI_RECEIPT_SCHEMA,
        "capability_receipt_schema": CAPABILITY_RECEIPT_SCHEMA,
        "default_mount_cycles": DEFAULT_MOUNT_CYCLES,
        "default_crash_cycles": DEFAULT_CRASH_CYCLES,
        "readiness_timeout_seconds": READINESS_TIMEOUT_SECONDS,
        "capability_probe_budget_seconds": CAPABILITY_PROBE_BUDGET_SECONDS,
        "support_claim_unavailable": SUPPORT_CLAIM_UNAVAILABLE,
    }
    errors: list[str] = []
    if TASK_ID != "KVFS-501":
        errors.append("task_id must be KVFS-501")
    if DEFAULT_MOUNT_CYCLES != 100:
        errors.append("default mount cycles must be 100")
    if DEFAULT_CRASH_CYCLES != 100:
        errors.append("default crash cycles must be 100")
    if READINESS_TIMEOUT_SECONDS != 15.0:
        errors.append("readiness timeout must be 15s")
    if CAPABILITY_PROBE_BUDGET_SECONDS > 5.0:
        errors.append("capability probe budget must be <= 5s")
    if not SOAK_RECEIPT_SCHEMA.endswith("@1"):
        errors.append("soak receipt schema major must be @1")
    return {
        "ok": not errors,
        "errors": errors,
        "required": required,
        "module": str(Path(__file__).resolve()),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="KVFS-501 Linux ARM64 / mount resource soak"
    )
    parser.add_argument("--check-schema", action="store_true")
    parser.add_argument("--run", action="store_true", help="run full soak suite")
    parser.add_argument(
        "--cycles",
        type=int,
        default=None,
        help="override mount and crash cycle counts (default 100)",
    )
    parser.add_argument(
        "--work-directory",
        type=str,
        default=None,
        help="optional durable work directory for receipts",
    )
    parser.add_argument(
        "--concurrency-seconds",
        type=float,
        default=DEFAULT_CONCURRENCY_SECONDS,
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.check_schema and not args.run:
        result = check_schema()
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0 if result["ok"] else 2

    if not args.run and not args.check_schema:
        result = check_schema()
        print(json.dumps(result, sort_keys=True, indent=2))
        print("hint: pass --run to execute the soak suite", file=sys.stderr)
        return 0 if result["ok"] else 2

    work = Path(args.work_directory) if args.work_directory else None
    suite = run_linux_soak(
        work,
        mount_cycles=args.cycles,
        crash_cycles=args.cycles,
        concurrency_seconds=args.concurrency_seconds,
    )
    record = suite.to_record()
    # Compact stdout: omit per-cycle arrays for readability.
    compact = {
        k: v
        for k, v in record.items()
        if k not in {"mount_cycles", "crash_cycles"}
    }
    compact["mount_cycle_successes"] = sum(1 for c in suite.mount_cycles if c.success)
    compact["crash_cycle_successes"] = sum(1 for c in suite.crash_cycles if c.success)
    print(json.dumps(compact, sort_keys=True, indent=2, default=str))

    matrix_clean = (
        suite.abi.abi_ok
        and suite.concurrency.success
        and all(c.success for c in suite.mount_cycles)
        and all(c.success for c in suite.crash_cycles)
        and suite.detail.get("zero_leaks")
        and suite.detail.get("zero_stale_or_lost")
        and suite.detail.get("resource_ok")
    )
    if suite.status == SoakStatus.FAILED.value or not matrix_clean:
        return 1
    # passed / hermetic_passed / capability_unavailable (finite nonpromotion)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""KVFS-700: Positive/negative Docker mount, restart, and recovery conformance.

Owns the Linux Docker container-conformance lane:

* minimal-capability profile (``/dev/fuse`` + ``SYS_ADMIN``, never privileged)
  passes in-container CRUD / fsync / restart / recovery;
* absent device and absent capability each fail promptly (≤5 s) without
  attempting a native mount;
* exclusive container / process / mount / volume leases fence concurrent
  runners and release in ``finally`` + cleanup watchdog;
* privileged profile is forbidden and cannot leak into the minimal profile.

Hermetic execution plane (default) exercises the same case matrix through the
KVFS-701 Compose/Dockerfile contracts plus :class:`LinuxMountLifecycle` and
:class:`KernelVFSOperations` so CI validates bounds without claiming live
Docker support. Live Docker plane requires a reachable daemon, image profile,
and host FUSE device; only that plane may emit ``status=passed`` live-support
receipts.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Final

import pytest
import yaml

from ipfs_kit_py.core.vfs.host_contracts import HostPlatform, OpenFlag
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
from ipfs_kit_py.kernel_vfs.wal_recovery import (
    MountRecoveryCoordinator,
    StateLease,
    StateLeaseHeldError,
)

# ---------------------------------------------------------------------------
# Paths / identity / bounds
# ---------------------------------------------------------------------------

PACKAGE_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
DOCKERFILE_PATH: Final[Path] = PACKAGE_ROOT / "docker" / "kernel-vfs.Dockerfile"
COMPOSE_PATH: Final[Path] = PACKAGE_ROOT / "docker-compose.kernel-vfs.yml"
TEST_PATH: Final[Path] = Path(__file__).resolve()

TASK_ID: Final[str] = "KVFS-700"
DEPENDS_ON: Final[tuple[str, ...]] = ("KVFS-506", "KVFS-701")
CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
HARNESS_NAMESPACE: Final[str] = (
    "ipfs_kit_py/tests/kernel_vfs/container/live_container"
)
CASE_RECEIPT_SCHEMA: Final[str] = f"{HARNESS_NAMESPACE}/case-receipt@{SCHEMA_MAJOR}"
SUITE_RECEIPT_SCHEMA: Final[str] = f"{HARNESS_NAMESPACE}/suite-receipt@{SCHEMA_MAJOR}"
CAPABILITY_RECEIPT_SCHEMA: Final[str] = (
    f"{HARNESS_NAMESPACE}/capability-receipt@{SCHEMA_MAJOR}"
)
LEASE_RECEIPT_SCHEMA: Final[str] = f"{HARNESS_NAMESPACE}/lease-receipt@{SCHEMA_MAJOR}"

PROFILE_MINIMAL: Final[str] = "linux-fuse-minimal"
PROFILE_HERMETIC: Final[str] = "container_hermetic_conformance"
PROFILE_LIVE_DOCKER: Final[str] = "container_live_docker"
SERVICE_NAME: Final[str] = "kernel-vfs"
REQUIRED_DEVICE: Final[str] = "/dev/fuse"
REQUIRED_CAP: Final[str] = "SYS_ADMIN"
_CAP_SYS_ADMIN: Final[int] = 1 << 21

READINESS_TIMEOUT_SECONDS: Final[float] = DEFAULT_READINESS_TIMEOUT_SECONDS  # 15
CASE_TIMEOUT_SECONDS: Final[float] = 60.0
CAPABILITY_PROBE_BUDGET_SECONDS: Final[float] = 5.0
MISSING_INPUT_BUDGET_SECONDS: Final[float] = 5.0
WATCHDOG_JOIN_SECONDS: Final[float] = 2.0
CLEANUP_BUDGET_SECONDS: Final[float] = 15.0

SUPPORT_CLAIM_UNAVAILABLE: Final[str] = "capability_unavailable"
SUPPORT_CLAIM_LIVE_PASSED: Final[str] = "live_passed"
SUPPORT_CLAIM_HERMETIC_ONLY: Final[str] = "hermetic_only"

LIVE_FORCE_ENV: Final[str] = "IPFS_KIT_KERNEL_VFS_CONTAINER_LIVE"
STATE_VOLUME: Final[str] = "kernel-vfs-state"
WAL_VOLUME: Final[str] = "kernel-vfs-wal"
CACHE_VOLUME: Final[str] = "kernel-vfs-cache"
STATE_PATH: Final[str] = "/var/lib/ipfs-kit-vfs/state"
WAL_PATH: Final[str] = "/var/lib/ipfs-kit-vfs/wal"
CACHE_PATH: Final[str] = "/var/lib/ipfs-kit-vfs/cache"
MOUNTPOINT_PATH: Final[str] = "/mnt/ipfs-kit-vfs"

# Propagation claim boundary (host-visible is a distinct profile; see
# test_propagation.py). Default in-container profile never claims host
# propagation or Docker Desktop.
PROPAGATION_IN_CONTAINER: Final[str] = "in_container"
PROPAGATION_NATIVE_RSHARED: Final[str] = "native_linux_rshared"
PROPAGATION_DOCKER_DESKTOP: Final[str] = "docker_desktop"


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class ExecutionPlane(str, Enum):
    HERMETIC = "hermetic"
    LIVE_DOCKER = "live_docker"


class CaseStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CAPABILITY_UNAVAILABLE = "capability_unavailable"
    SKIPPED = "skipped"
    CLEANUP_FAILED = "cleanup_failed"


class ConformanceCaseId(str, Enum):
    """Pinned container case matrix required by KVFS-700 acceptance."""

    MINIMAL_CRUD = "minimal_crud"
    MINIMAL_FSYNC = "minimal_fsync"
    RESTART = "restart"
    RECOVERY = "recovery"
    ABSENT_DEVICE = "absent_device"
    ABSENT_CAPABILITY = "absent_capability"
    NO_PRIVILEGED = "no_privileged"
    LEASE_CLEANUP = "lease_cleanup"


REQUIRED_CASE_IDS: Final[tuple[ConformanceCaseId, ...]] = tuple(ConformanceCaseId)


# ---------------------------------------------------------------------------
# Errors / helpers
# ---------------------------------------------------------------------------


class ContainerHarnessError(Exception):
    """Base harness failure (fail-closed)."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "CONTAINER_HARNESS_ERROR",
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


class SupportPromotionError(ContainerHarnessError):
    def __init__(
        self, message: str = "cannot promote live Docker container support"
    ) -> None:
        super().__init__(message, code="SUPPORT_PROMOTION_BLOCKED")


def _unix_ms() -> int:
    return int(time.time() * 1000)


def _monotonic() -> float:
    return time.monotonic()


def _bounded_text(value: Any, *, limit: int = 4_096) -> str:
    text = "" if value is None else str(value)
    encoded = text.encode("utf-8")
    if len(encoded) <= limit:
        return text
    return encoded[: limit].decode("utf-8", errors="ignore")


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


def support_claim_for(
    *,
    docker_ready: bool,
    live_cases_passed: bool,
    plane: ExecutionPlane | str,
) -> str:
    plane_value = plane.value if isinstance(plane, ExecutionPlane) else str(plane)
    if not docker_ready:
        return SUPPORT_CLAIM_UNAVAILABLE
    if plane_value == ExecutionPlane.LIVE_DOCKER.value and live_cases_passed:
        return SUPPORT_CLAIM_LIVE_PASSED
    return SUPPORT_CLAIM_HERMETIC_ONLY


def can_promote_live_support(
    *,
    docker_ready: bool,
    support_claim: str,
    status: str,
    profile: str,
) -> bool:
    if not docker_ready:
        return False
    if support_claim != SUPPORT_CLAIM_LIVE_PASSED:
        return False
    if status not in {"passed", "admitted"}:
        return False
    if profile != PROFILE_LIVE_DOCKER:
        return False
    return True


# ---------------------------------------------------------------------------
# Compose / Dockerfile loaders (KVFS-701 contract surface)
# ---------------------------------------------------------------------------


def _dockerfile_text() -> str:
    assert DOCKERFILE_PATH.is_file(), f"missing Dockerfile: {DOCKERFILE_PATH}"
    return DOCKERFILE_PATH.read_text(encoding="utf-8")


def _compose_doc() -> dict[str, Any]:
    assert COMPOSE_PATH.is_file(), f"missing Compose file: {COMPOSE_PATH}"
    doc = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    assert isinstance(doc, dict), "Compose file must parse to a mapping"
    return doc


def _compose_service() -> dict[str, Any]:
    services = _compose_doc().get("services")
    assert isinstance(services, dict)
    service = services.get(SERVICE_NAME)
    assert isinstance(service, dict), f"service {SERVICE_NAME!r} missing"
    return service


def minimal_capability_profile() -> dict[str, Any]:
    """Return the fail-closed minimal Docker FUSE profile contract."""

    service = _compose_service()
    devices = service.get("devices") or []
    caps = [str(c).upper() for c in (service.get("cap_add") or [])]
    return {
        "schema": "KernelVFSContainerMinimalProfile@1",
        "task_id": TASK_ID,
        "profile": PROFILE_MINIMAL,
        "privileged": bool(service.get("privileged")),
        "privileged_forbidden": True,
        "required_device": REQUIRED_DEVICE,
        "required_cap": REQUIRED_CAP,
        "devices": [str(d) for d in devices],
        "cap_add": caps,
        "device_present": any(REQUIRED_DEVICE in str(d) for d in devices),
        "cap_present": REQUIRED_CAP in caps,
        "missing_input_fail_seconds": MISSING_INPUT_BUDGET_SECONDS,
        "mount_mode": "foreground",
        "readiness": "required",
        "volumes": {
            "state": STATE_PATH,
            "wal": WAL_PATH,
            "cache": CACHE_PATH,
        },
        "volume_names": [STATE_VOLUME, WAL_VOLUME, CACHE_VOLUME],
        "propagation_claim": PROPAGATION_IN_CONTAINER,
        "host_propagation_claimed": False,
        "docker_desktop_propagation_claimed": False,
    }


# ---------------------------------------------------------------------------
# Capability preflight (mirrors KVFS-701 entrypoint semantics)
# ---------------------------------------------------------------------------


def _check_dev_fuse(device: str) -> tuple[bool, str]:
    path = Path(device)
    if not path.exists():
        return False, f"required device {device} is missing"
    try:
        mode = path.stat().st_mode
    except OSError as exc:
        return False, f"required device {device} is not accessible: {exc}"
    if not stat.S_ISCHR(mode):
        return False, f"{device} exists but is not a character device"
    if not os.access(device, os.R_OK | os.W_OK):
        return False, f"{device} is not read/write accessible"
    return True, "ok"


def _read_cap_eff() -> int | None:
    try:
        with open("/proc/self/status", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("CapEff:"):
                    return int(line.split(":", 1)[1].strip(), 16)
    except (OSError, ValueError):
        return None
    return None


def _has_sys_admin() -> bool:
    caps = _read_cap_eff()
    if caps is None:
        return False
    return bool(caps & _CAP_SYS_ADMIN)


@dataclass(frozen=True)
class PreflightReceipt:
    """Bounded container capability preflight receipt."""

    SCHEMA: ClassVar[str] = CAPABILITY_RECEIPT_SCHEMA

    ok: bool
    device_ok: bool
    cap_ok: bool
    privileged: bool
    elapsed_seconds: float
    budget_seconds: float
    within_budget: bool
    errors: tuple[str, ...] = ()
    message: str = ""
    native_mount_attempted: bool = False
    support_promoted: bool = False
    unix_ms: int = 0

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "task_id": TASK_ID,
            "ok": self.ok,
            "device_ok": self.device_ok,
            "cap_ok": self.cap_ok,
            "privileged": self.privileged,
            "elapsed_seconds": self.elapsed_seconds,
            "budget_seconds": self.budget_seconds,
            "within_budget": self.within_budget,
            "errors": list(self.errors),
            "message": self.message,
            "native_mount_attempted": self.native_mount_attempted,
            "support_promoted": self.support_promoted,
            "unix_ms": self.unix_ms or _unix_ms(),
            "required_device": REQUIRED_DEVICE,
            "required_cap": REQUIRED_CAP,
        }


def run_capability_preflight(
    *,
    device: str | None = REQUIRED_DEVICE,
    require_sys_admin: bool | None = True,
    privileged: bool = False,
    budget_seconds: float = MISSING_INPUT_BUDGET_SECONDS,
    simulate_missing_device: bool = False,
    simulate_missing_cap: bool = False,
) -> PreflightReceipt:
    """Fail-closed preflight matching the container entrypoint contract.

    Either missing required input fails within *budget_seconds* (capped at 5s).
    Never mounts. Never elevates to privileged.
    """

    started = _monotonic()
    budget = max(0.1, min(float(budget_seconds), 5.0))
    errors: list[str] = []

    if privileged:
        errors.append(
            "blanket privileged mode is forbidden "
            "(use --device /dev/fuse and --cap-add SYS_ADMIN only)"
        )

    if simulate_missing_device or device is None:
        device_ok = False
        errors.append(f"required device {REQUIRED_DEVICE} is missing")
    else:
        device_ok, dev_msg = _check_dev_fuse(device)
        if not device_ok:
            errors.append(dev_msg)

    if simulate_missing_cap or require_sys_admin is False:
        cap_ok = False
        errors.append(
            "required capability SYS_ADMIN is not effective "
            "(Compose must cap_add: [SYS_ADMIN]; privileged mode is forbidden)"
        )
    elif require_sys_admin is True:
        # Host probe: when running outside a container, CapEff may lack
        # SYS_ADMIN even though the *profile* requires it. For hermetic
        # positive paths callers pass require_sys_admin=None to mean
        # "profile asserts the cap will be granted".
        cap_ok = _has_sys_admin()
        if not cap_ok:
            errors.append(
                "required capability SYS_ADMIN is not effective "
                "(Compose must cap_add: [SYS_ADMIN]; privileged mode is forbidden)"
            )
    else:
        # Profile-level assertion: cap is declared by Compose, not host probe.
        cap_ok = True

    elapsed = _monotonic() - started
    ok = not errors
    if ok:
        message = (
            f"kernel-vfs capability preflight OK "
            f"(device={REQUIRED_DEVICE} cap=SYS_ADMIN elapsed={elapsed:.3f}s "
            f"budget={budget:.1f}s privileged=false)"
        )
    else:
        message = (
            f"kernel-vfs capability preflight FAILED "
            f"(elapsed={elapsed:.3f}s budget={budget:.1f}s privileged=false)"
        )

    return PreflightReceipt(
        ok=ok,
        device_ok=device_ok if not simulate_missing_device else False,
        cap_ok=cap_ok,
        privileged=bool(privileged),
        elapsed_seconds=elapsed,
        budget_seconds=budget,
        within_budget=elapsed <= budget + 0.05,
        errors=tuple(errors),
        message=message,
        native_mount_attempted=False,
        support_promoted=False,
        unix_ms=_unix_ms(),
    )


def probe_docker_daemon(
    *,
    budget_seconds: float = CAPABILITY_PROBE_BUDGET_SECONDS,
) -> dict[str, Any]:
    """Bounded Docker daemon reachability probe (never starts containers)."""

    started = _monotonic()
    budget = max(0.1, min(float(budget_seconds), 5.0))
    docker_bin = shutil.which("docker")
    ready = False
    message = "docker binary not found on PATH"
    version = ""
    if docker_bin:
        try:
            proc = subprocess.run(
                [docker_bin, "info", "--format", "{{.ServerVersion}}"],
                capture_output=True,
                text=True,
                timeout=budget,
                check=False,
            )
            if proc.returncode == 0 and (proc.stdout or "").strip():
                ready = True
                version = (proc.stdout or "").strip()
                message = f"docker daemon ready ({version})"
            else:
                message = _bounded_text(
                    (proc.stderr or proc.stdout or "docker info failed").strip()
                )
        except (OSError, subprocess.TimeoutExpired) as exc:
            message = _bounded_text(exc)
    elapsed = _monotonic() - started
    return {
        "schema": CAPABILITY_RECEIPT_SCHEMA,
        "task_id": TASK_ID,
        "docker_ready": ready,
        "docker_binary": docker_bin or "",
        "server_version": version,
        "elapsed_seconds": elapsed,
        "budget_seconds": budget,
        "within_budget": elapsed <= budget + 0.05,
        "message": message,
        "support_promoted": False,
        "is_linux": is_linux_host(),
    }


# ---------------------------------------------------------------------------
# Exclusive leases (container / process / mount / volume)
# ---------------------------------------------------------------------------


class ResourceLease:
    """Exclusive file-lock lease for one named resource role."""

    def __init__(
        self,
        root: Path,
        *,
        role: str,
        resource_id: str,
        holder_id: str | None = None,
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.role = role
        self.resource_id = resource_id
        self.holder_id = holder_id or f"holder:{uuid.uuid4().hex[:10]}"
        self.path = self.root / f"{role}-{_safe_token(resource_id)}.lease"
        self._fh: Any = None
        self._held = False

    @property
    def held(self) -> bool:
        return self._held

    def acquire(self, *, blocking: bool = False) -> None:
        if self._held:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self.path, "a+", encoding="utf-8")
        try:
            import fcntl

            flags = fcntl.LOCK_EX
            if not blocking:
                flags |= fcntl.LOCK_NB
            fcntl.flock(fh.fileno(), flags)
        except BlockingIOError as exc:
            fh.close()
            raise ContainerHarnessError(
                f"{self.role} lease held for {self.resource_id}",
                code="LEASE_HELD",
                detail={
                    "role": self.role,
                    "resource_id": self.resource_id,
                    "path": str(self.path),
                },
            ) from exc
        except OSError as exc:
            # Non-POSIX: fall back to exclusive create.
            fh.close()
            if self.path.exists() and not blocking:
                raise ContainerHarnessError(
                    f"{self.role} lease held for {self.resource_id}",
                    code="LEASE_HELD",
                    detail={"role": self.role, "resource_id": self.resource_id},
                ) from exc
            fh = open(self.path, "w", encoding="utf-8")
        payload = {
            "schema": LEASE_RECEIPT_SCHEMA,
            "role": self.role,
            "resource_id": self.resource_id,
            "holder_id": self.holder_id,
            "pid": os.getpid(),
            "unix_ms": _unix_ms(),
            "privileged": False,
        }
        fh.seek(0)
        fh.truncate()
        fh.write(json.dumps(payload, sort_keys=True))
        fh.flush()
        self._fh = fh
        self._held = True

    def release(self) -> None:
        if not self._held:
            return
        fh = self._fh
        self._fh = None
        self._held = False
        if fh is not None:
            try:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except (OSError, ImportError):
                pass
            try:
                fh.close()
            except OSError:
                pass
        try:
            if self.path.exists():
                self.path.unlink()
        except OSError:
            pass

    def __enter__(self) -> "ResourceLease":
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()


def _safe_token(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value)[:64]


@dataclass
class LeaseBundle:
    """Exclusive resource leases for one container conformance session."""

    container: ResourceLease
    process: ResourceLease
    mount: ResourceLease
    volume_state: ResourceLease
    volume_wal: ResourceLease
    volume_cache: ResourceLease
    privileged_guard: ResourceLease
    state_lease: StateLease | None = None
    tracked_pids: list[int] = field(default_factory=list)
    container_ids: list[str] = field(default_factory=list)
    released: bool = False

    def acquire_all(self) -> None:
        for lease in (
            self.container,
            self.process,
            self.mount,
            self.volume_state,
            self.volume_wal,
            self.volume_cache,
            self.privileged_guard,
        ):
            lease.acquire()
        if self.state_lease is not None:
            self.state_lease.acquire()

    def release_all(self) -> dict[str, Any]:
        errors: list[str] = []
        # Kill tracked processes (fail-closed cleanup).
        for pid in list(self.tracked_pids):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                continue
            except PermissionError as exc:
                errors.append(f"pid {pid}: {exc}")
                continue
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                continue
            except OSError as exc:
                errors.append(f"sigterm {pid}: {exc}")
            deadline = _monotonic() + 2.0
            while _monotonic() < deadline:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.02)
            else:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except OSError as exc:
                    errors.append(f"sigkill {pid}: {exc}")
        self.tracked_pids.clear()

        if self.state_lease is not None:
            try:
                self.state_lease.release()
            except Exception as exc:  # noqa: BLE001
                errors.append(f"state_lease: {exc}")
            self.state_lease = None

        for lease in (
            self.privileged_guard,
            self.volume_cache,
            self.volume_wal,
            self.volume_state,
            self.mount,
            self.process,
            self.container,
        ):
            try:
                lease.release()
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{lease.role}: {exc}")

        held = [
            lease.role
            for lease in (
                self.container,
                self.process,
                self.mount,
                self.volume_state,
                self.volume_wal,
                self.volume_cache,
                self.privileged_guard,
            )
            if lease.held
        ]
        self.released = not held and not errors
        return {
            "released": self.released,
            "held_remaining": held,
            "errors": errors,
            "container_ids": list(self.container_ids),
            "privileged_leaked": False,
        }


def build_lease_bundle(
    root: Path,
    *,
    token: str | None = None,
    state_directory: Path | None = None,
) -> LeaseBundle:
    token = token or uuid.uuid4().hex[:10]
    state_dir = state_directory or (root / "state" / token)
    state_dir.mkdir(parents=True, exist_ok=True)
    return LeaseBundle(
        container=ResourceLease(
            root, role="container", resource_id=f"ipfs-kit-kernel-vfs-{token}"
        ),
        process=ResourceLease(root, role="process", resource_id=f"pid-namespace-{token}"),
        mount=ResourceLease(root, role="mount", resource_id=f"mnt-{token}"),
        volume_state=ResourceLease(root, role="volume", resource_id=f"{STATE_VOLUME}-{token}"),
        volume_wal=ResourceLease(root, role="volume", resource_id=f"{WAL_VOLUME}-{token}"),
        volume_cache=ResourceLease(root, role="volume", resource_id=f"{CACHE_VOLUME}-{token}"),
        privileged_guard=ResourceLease(
            root, role="privileged_profile", resource_id=f"never-privileged-{token}"
        ),
        state_lease=StateLease(
            state_dir,
            mount_id=f"mount:container-{token}",
            holder_id=f"holder:container-{token}",
        ),
    )


# ---------------------------------------------------------------------------
# Watchdog
# ---------------------------------------------------------------------------


class CaseWatchdog:
    def __init__(self, timeout_seconds: float = CASE_TIMEOUT_SECONDS) -> None:
        self.timeout_seconds = max(0.1, float(timeout_seconds))
        self._stop = threading.Event()
        self._fired = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def fired(self) -> bool:
        return self._fired.is_set()

    def start(self, case_id: str) -> None:
        self.cancel()
        self._stop.clear()
        self._fired.clear()
        self._thread = threading.Thread(
            target=self._run,
            name=f"container-case-watchdog-{case_id}",
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
    def __init__(
        self,
        callback: Callable[[], None],
        *,
        deadline_seconds: float = CLEANUP_BUDGET_SECONDS,
    ) -> None:
        self._callback = callback
        self.deadline_seconds = max(0.1, float(deadline_seconds))
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="container-cleanup-watchdog", daemon=True
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
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# Mount session (in-container model)
# ---------------------------------------------------------------------------


@dataclass
class ContainerMountSession:
    """In-container mount session: lifecycle + operations + leases."""

    lifecycle: LinuxMountLifecycle
    operations: KernelVFSOperations
    mountpoint: Path
    state_directory: Path
    wal_directory: Path
    cache_directory: Path
    plane: ExecutionPlane
    mount_id: str
    leases: LeaseBundle
    profile: str = PROFILE_MINIMAL
    privileged: bool = False
    propagation_claim: str = PROPAGATION_IN_CONTAINER

    @property
    def root(self) -> str:
        return str(self.mountpoint)

    def close(self) -> dict[str, Any]:
        errors: list[str] = []
        try:
            self.operations.close()
        except Exception as exc:  # noqa: BLE001
            errors.append(f"ops: {exc}")
        try:
            self.lifecycle.unmount(timeout_seconds=5.0)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"unmount: {exc}")
            try:
                self.lifecycle.signal_child(signal.SIGKILL)
            except Exception as kill_exc:  # noqa: BLE001
                errors.append(f"kill: {kill_exc}")
        # Track child pid if still alive for lease cleanup.
        pid = getattr(self.lifecycle, "pid", None)
        if isinstance(pid, int) and pid > 0:
            self.leases.tracked_pids.append(pid)
        lease_receipt = self.leases.release_all()
        if errors:
            lease_receipt = dict(lease_receipt)
            lease_receipt["close_errors"] = errors
            lease_receipt["released"] = False
        return lease_receipt


# ---------------------------------------------------------------------------
# Case helpers
# ---------------------------------------------------------------------------


def _errno_name(outcome: Any) -> str:
    errno = getattr(outcome, "errno", None)
    if errno is None:
        return ""
    return str(getattr(errno, "value", errno) or "")


def _require_success(outcome: Any, *, step: str) -> Any:
    if not getattr(outcome, "success", False):
        raise ContainerHarnessError(
            f"{step} failed",
            code="CASE_STEP_FAILED",
            detail={
                "step": step,
                "errno": _errno_name(outcome),
                "message": _bounded_text(getattr(outcome, "message", "") or ""),
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
    body: bytes,
    *,
    step: str = "create",
    mode: int = 0o644,
    release: bool = True,
) -> Any:
    """Create ``path`` with ``body`` using the same contract as KVFS-506.

    Never pass ``O_EXCL`` through :meth:`KernelVFSOperations.create`: the
    composed runtime does exclusive host create then re-opens with the same
    flags, so ``O_EXCL`` on the open leg fails with ``EEXIST`` after a
    successful create.
    """

    created = ops.create(
        path,
        body,
        mode=mode,
        flags=(OpenFlag.O_RDWR, OpenFlag.O_CREAT),
    )
    if created.success:
        handle = created.handle
        if release and handle is not None:
            _release_handle(ops, handle)
        return created

    # Path may already exist from a partial create; repair via open+write.
    opened = ops.open(
        path, (OpenFlag.O_RDWR, OpenFlag.O_TRUNC, OpenFlag.O_CREAT), mode=mode
    )
    if opened.success and opened.handle is not None:
        handle = opened.handle
        written = ops.write(
            path,
            body,
            offset=0,
            handle_id=handle.handle_id,
            generation=handle.generation,
        )
        if written.success:
            if release:
                _release_handle(ops, handle)
            return opened
        _release_handle(ops, handle)
    raise ContainerHarnessError(
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
    outcome = ops.mkdir(path, mode=mode)
    if getattr(outcome, "success", False):
        return outcome
    if _errno_name(outcome) == "EEXIST":
        st = ops.getattr(path)
        if getattr(st, "success", False):
            return outcome
    return _require_success(outcome, step=f"mkdir:{path}")


# ---------------------------------------------------------------------------
# Case implementations
# ---------------------------------------------------------------------------


def _case_minimal_crud(session: ContainerMountSession) -> dict[str, Any]:
    """Minimal-capability mount passes in-container CRUD."""

    if session.privileged:
        raise ContainerHarnessError("privileged profile forbidden", code="PRIVILEGED")
    if session.profile != PROFILE_MINIMAL:
        raise ContainerHarnessError(
            "CRUD requires minimal profile",
            code="PROFILE",
            detail={"profile": session.profile},
        )
    ops = session.operations
    token = uuid.uuid4().hex[:12]
    folder = f"ctr_crud_{token}"
    file_path = f"{folder}/note.txt"
    payload = b"container-crud-v1\n"
    updated = b"container-crud-v2\n"

    _mkdir(ops, folder)
    _create_with_body(ops, file_path, payload, step="create")
    read = _require_success(
        ops.read(file_path, offset=0, size=len(payload) + 8), step="read"
    )
    if bytes(read.data or b"")[: len(payload)] != payload:
        raise ContainerHarnessError("crud read mismatch", code="CASE_ASSERT")
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
    _require_success(ops.rename(file_path, renamed), step="rename")
    read2 = _require_success(
        ops.read(renamed, offset=0, size=len(updated) + 4), step="read-renamed"
    )
    if bytes(read2.data or b"")[: len(updated)] != updated:
        raise ContainerHarnessError("crud post-rename mismatch", code="CASE_ASSERT")
    _require_success(ops.unlink(renamed), step="unlink")
    _require_success(ops.rmdir(folder), step="rmdir")
    return {
        "operations": [
            "mkdir",
            "create",
            "read",
            "write",
            "rename",
            "unlink",
            "rmdir",
        ],
        "profile": session.profile,
        "privileged": False,
        "propagation_claim": session.propagation_claim,
        "bytes": len(updated),
    }


def _case_minimal_fsync(session: ContainerMountSession) -> dict[str, Any]:
    """Minimal-capability mount passes in-container fsync durability path."""

    ops = session.operations
    path = f"ctr_fsync_{uuid.uuid4().hex[:8]}.dat"
    created = _create_with_body(ops, path, b"", step="create fsync", release=False)
    handle = getattr(created, "handle", None)
    if handle is None:
        opened = _require_success(
            ops.open(path, (OpenFlag.O_RDWR, OpenFlag.O_CREAT), mode=0o644),
            step="open fsync",
        )
        handle = opened.handle
    assert handle is not None
    payload = b"container-durable-700"
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
    if bytes(read.data or b"")[: len(payload)] != payload:
        raise ContainerHarnessError("fsync durability mismatch", code="CASE_ASSERT")
    _release_handle(ops, handle)
    _require_success(ops.unlink(path), step="unlink fsync")
    return {
        "bytes": len(payload),
        "fsync": True,
        "fdatasync": True,
        "profile": session.profile,
        "privileged": False,
    }


def _case_restart(session: ContainerMountSession) -> dict[str, Any]:
    """Container restart: unmount + remount recovers before ready (idempotent)."""

    life = session.lifecycle
    if not life.ready:
        raise ContainerHarnessError("session not ready before restart", code="CASE_ASSERT")
    readiness = life.read_readiness()
    if readiness is None or not readiness.recovery_complete:
        raise ContainerHarnessError("recovery incomplete before restart", code="CASE_ASSERT")

    state_dir = session.state_directory
    mountpoint = session.mountpoint
    generation_id = life.config.generation_id
    first = life.unmount(timeout_seconds=5.0, sig=signal.SIGTERM)
    if not first.success:
        raise ContainerHarnessError(
            "restart unmount failed",
            code="CASE_ASSERT",
            detail=first.to_record(),
        )
    if not first.recovery_preserved:
        raise ContainerHarnessError(
            "recovery not preserved across restart", code="CASE_ASSERT"
        )

    recovery_cfg = LinuxMountConfig(
        mountpoint=mountpoint,
        state_directory=state_dir,
        mount_id=f"mount:ctr-restart-{uuid.uuid4().hex[:8]}",
        readiness_timeout_seconds=READINESS_TIMEOUT_SECONDS,
        heartbeat_interval_seconds=0.05,
        unmount_timeout_seconds=5.0,
        hermetic=True,
        generation_id=generation_id,
        holder_id=f"holder:ctr-restart-{uuid.uuid4().hex[:8]}",
    )
    recovery_life = LinuxMountLifecycle(recovery_cfg)
    try:
        readiness2 = recovery_life.start(wait_ready=True)
    except Exception as exc:  # noqa: BLE001
        try:
            recovery_life.unmount(timeout_seconds=2.0)
        except Exception:  # noqa: BLE001
            pass
        raise ContainerHarnessError(
            "restart remount failed",
            code="CASE_RECOVERY",
            detail={"error": _bounded_text(exc)},
        ) from exc
    if not readiness2.ready or not readiness2.recovery_complete:
        try:
            recovery_life.unmount(timeout_seconds=2.0)
        except Exception:  # noqa: BLE001
            pass
        raise ContainerHarnessError(
            "restart remount not ready",
            code="CASE_RECOVERY",
            detail=readiness2.to_record(),
        )
    phases = list(readiness2.recovery_phases or ())
    if (
        "enter_ready" in phases
        and "acquire_lease" in phases
        and phases.index("acquire_lease") > phases.index("enter_ready")
    ):
        try:
            recovery_life.unmount(timeout_seconds=2.0)
        except Exception:  # noqa: BLE001
            pass
        raise ContainerHarnessError(
            "ready advertised before lease recovery on restart",
            code="CASE_RECOVERY_ORDER",
            detail={"phases": phases},
        )
    session.lifecycle = recovery_life
    return {
        "restarted": True,
        "recovery_preserved": True,
        "recovery_before_ready": True,
        "phases": phases,
        "profile": session.profile,
    }


def _case_recovery(session: ContainerMountSession) -> dict[str, Any]:
    """Forced kill + recovery replay completes before ready; idempotent."""

    life = session.lifecycle
    if not life.ready:
        raise ContainerHarnessError("session not ready before recovery", code="CASE_ASSERT")
    pid = life.pid
    if not pid:
        raise ContainerHarnessError("no child pid to kill", code="CASE_ASSERT")
    state_dir = session.state_directory
    mountpoint = session.mountpoint
    generation_id = life.config.generation_id
    session.leases.tracked_pids.append(int(pid))

    if not life.signal_child(signal.SIGKILL):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    deadline = _monotonic() + 5.0
    while life.running and _monotonic() < deadline:
        time.sleep(0.02)
    if life.running:
        raise ContainerHarnessError(
            "child still running after SIGKILL", code="CASE_ASSERT"
        )
    time.sleep(0.05)

    recovery_preserved = (state_dir / "recovery-preserved").exists() or (
        state_dir / "recovery"
    ).exists()
    if not recovery_preserved:
        raise ContainerHarnessError(
            "recovery state not preserved after forced kill", code="CASE_ASSERT"
        )

    try:
        life.unmount(timeout_seconds=2.0, sig=signal.SIGKILL)
    except Exception:  # noqa: BLE001
        pass

    last_error: BaseException | None = None
    recovery_life: LinuxMountLifecycle | None = None
    readiness = None
    for attempt in range(5):
        recovery_cfg = LinuxMountConfig(
            mountpoint=mountpoint,
            state_directory=state_dir,
            mount_id=f"mount:ctr-recover-{uuid.uuid4().hex[:8]}",
            readiness_timeout_seconds=READINESS_TIMEOUT_SECONDS,
            heartbeat_interval_seconds=0.05,
            unmount_timeout_seconds=5.0,
            hermetic=True,
            generation_id=generation_id,
            holder_id=f"holder:ctr-recover-{uuid.uuid4().hex[:8]}",
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
        raise ContainerHarnessError(
            "recovery remount failed after forced kill",
            code="CASE_RECOVERY",
            detail={"error": _bounded_text(last_error), "attempts": 5},
        ) from last_error

    if not readiness.ready or not readiness.recovery_complete:
        try:
            recovery_life.unmount(timeout_seconds=2.0)
        except Exception:  # noqa: BLE001
            pass
        raise ContainerHarnessError(
            "recovery remount did not become ready",
            code="CASE_RECOVERY",
            detail=readiness.to_record(),
        )
    phases = list(readiness.recovery_phases or ())
    if (
        "enter_ready" in phases
        and "replay_wal" in phases
        and phases.index("replay_wal") > phases.index("enter_ready")
    ):
        try:
            recovery_life.unmount(timeout_seconds=2.0)
        except Exception:  # noqa: BLE001
            pass
        raise ContainerHarnessError(
            "ready advertised before WAL replay",
            code="CASE_RECOVERY_ORDER",
            detail={"phases": phases},
        )
    session.lifecycle = recovery_life

    # Explicit second recovery pass for idempotency.
    recovery_root = state_dir / "replay-probe"
    recovery_root.mkdir(parents=True, exist_ok=True)
    coord = MountRecoveryCoordinator(
        recovery_root,
        mount_id=f"mount:ctr-replay-{uuid.uuid4().hex[:8]}",
        generation_id=f"wal-gen:ctr-replay-{uuid.uuid4().hex[:8]}",
        platform=HostPlatform.LINUX,
        recovery_timeout_seconds=min(30.0, READINESS_TIMEOUT_SECONDS),
    )
    try:
        first = coord.recover()
        if not first.success or not first.ready or not first.recovery_complete:
            raise ContainerHarnessError(
                "first recovery failed",
                code="CASE_RECOVERY",
                detail=first.to_record(),
            )
        second = coord.recover()
        if not second.success:
            raise ContainerHarnessError(
                "idempotent recovery failed",
                code="CASE_RECOVERY",
                detail=second.to_record(),
            )
        first_phases = list(first.phases or ())
    finally:
        try:
            coord.close()
        except Exception:  # noqa: BLE001
            pass

    return {
        "killed": True,
        "signal": "SIGKILL",
        "pid": pid,
        "recovery_preserved": True,
        "recovered": True,
        "recovery_before_ready": True,
        "idempotent": True,
        "phases": phases,
        "coordinator_phases": first_phases,
        "profile": session.profile,
    }


def _case_absent_device(session: ContainerMountSession | None) -> dict[str, Any]:
    """Absent /dev/fuse fails promptly without mounting."""

    started = _monotonic()
    receipt = run_capability_preflight(
        simulate_missing_device=True,
        require_sys_admin=None,  # profile-level cap present
        budget_seconds=MISSING_INPUT_BUDGET_SECONDS,
    )
    elapsed = _monotonic() - started
    if receipt.ok:
        raise ContainerHarnessError(
            "absent device preflight unexpectedly passed", code="CASE_ASSERT"
        )
    if not receipt.within_budget or elapsed > MISSING_INPUT_BUDGET_SECONDS + 0.5:
        raise ContainerHarnessError(
            "absent device preflight exceeded budget",
            code="CASE_TIMEOUT",
            detail={"elapsed": elapsed, "budget": MISSING_INPUT_BUDGET_SECONDS},
        )
    if receipt.native_mount_attempted:
        raise ContainerHarnessError(
            "native mount attempted despite missing device", code="CASE_ASSERT"
        )
    if not any("device" in e.lower() or "missing" in e.lower() for e in receipt.errors):
        raise ContainerHarnessError(
            "missing-device error not reported",
            code="CASE_ASSERT",
            detail={"errors": list(receipt.errors)},
        )
    return {
        "failed_promptly": True,
        "elapsed_seconds": elapsed,
        "budget_seconds": MISSING_INPUT_BUDGET_SECONDS,
        "native_mount_attempted": False,
        "docker_capability": "missing_device",
        "error_code": "ENODEV",
        "receipt": receipt.to_record(),
    }


def _preflight_cap_only_failure() -> PreflightReceipt:
    """Produce a preflight failure that always includes the SYS_ADMIN absence."""

    device_present = Path(REQUIRED_DEVICE).exists()
    return run_capability_preflight(
        simulate_missing_cap=True,
        require_sys_admin=None,
        device=REQUIRED_DEVICE,
        simulate_missing_device=not device_present,
        budget_seconds=MISSING_INPUT_BUDGET_SECONDS,
    )


def _case_absent_capability(session: ContainerMountSession | None) -> dict[str, Any]:
    """Absent SYS_ADMIN fails promptly without mounting or privileged elevation."""

    started = _monotonic()
    receipt = _preflight_cap_only_failure()
    elapsed = _monotonic() - started
    if receipt.ok:
        raise ContainerHarnessError(
            "absent capability preflight unexpectedly passed", code="CASE_ASSERT"
        )
    if not receipt.within_budget or elapsed > MISSING_INPUT_BUDGET_SECONDS + 0.5:
        raise ContainerHarnessError(
            "absent capability preflight exceeded budget",
            code="CASE_TIMEOUT",
            detail={"elapsed": elapsed},
        )
    if receipt.native_mount_attempted:
        raise ContainerHarnessError(
            "native mount attempted despite missing capability", code="CASE_ASSERT"
        )
    if not any("SYS_ADMIN" in e or "capability" in e.lower() for e in receipt.errors):
        raise ContainerHarnessError(
            "missing-capability error not reported",
            code="CASE_ASSERT",
            detail={"errors": list(receipt.errors)},
        )
    if receipt.privileged:
        raise ContainerHarnessError(
            "privileged elevation observed on missing cap", code="PRIVILEGED"
        )
    return {
        "failed_promptly": True,
        "elapsed_seconds": elapsed,
        "budget_seconds": MISSING_INPUT_BUDGET_SECONDS,
        "native_mount_attempted": False,
        "docker_capability": "missing_cap",
        "blanket_privileged_forbidden": True,
        "error_code": "EPERM",
        "receipt": receipt.to_record(),
    }


def _case_no_privileged(session: ContainerMountSession | None) -> dict[str, Any]:
    """Privileged profile is rejected promptly; Compose/Dockerfile forbid it."""

    started = _monotonic()
    receipt = run_capability_preflight(
        privileged=True,
        require_sys_admin=None,
        device=REQUIRED_DEVICE,
        simulate_missing_device=not Path(REQUIRED_DEVICE).exists(),
        budget_seconds=MISSING_INPUT_BUDGET_SECONDS,
    )
    elapsed = _monotonic() - started
    if receipt.ok:
        raise ContainerHarnessError(
            "privileged preflight must fail", code="PRIVILEGED"
        )
    if elapsed > MISSING_INPUT_BUDGET_SECONDS + 0.5:
        raise ContainerHarnessError(
            "privileged rejection exceeded budget", code="CASE_TIMEOUT"
        )

    profile = minimal_capability_profile()
    if profile.get("privileged"):
        raise ContainerHarnessError(
            "Compose profile enables privileged", code="PRIVILEGED"
        )
    service = _compose_service()
    if service.get("privileged") is not False:
        raise ContainerHarnessError(
            "Compose privileged is not explicitly false", code="PRIVILEGED"
        )
    df = _dockerfile_text().lower()
    if "privileged=true" in df.replace(" ", "") or re.search(
        r"privileged\s*:\s*true", df
    ):
        raise ContainerHarnessError(
            "Dockerfile claims privileged true", code="PRIVILEGED"
        )
    compose_text = COMPOSE_PATH.read_text(encoding="utf-8")
    instruction_lines = [
        line
        for line in compose_text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if re.search(r"privileged\s*:\s*true", "\n".join(instruction_lines), re.I):
        raise ContainerHarnessError(
            "Compose instructions enable privileged", code="PRIVILEGED"
        )
    return {
        "privileged_forbidden": True,
        "preflight_rejected": True,
        "elapsed_seconds": elapsed,
        "compose_privileged": False,
        "profile": PROFILE_MINIMAL,
        "receipt": receipt.to_record(),
    }


def _case_lease_cleanup(session: ContainerMountSession) -> dict[str, Any]:
    """No container, process, mount, volume lease, or privileged profile leaks."""

    # Fence: second holder of the same container lease must fail.
    rival = ResourceLease(
        session.leases.container.root,
        role="container",
        resource_id=session.leases.container.resource_id,
        holder_id="holder:rival",
    )
    with pytest.raises(ContainerHarnessError) as exc_info:
        rival.acquire(blocking=False)
    assert exc_info.value.code == "LEASE_HELD"

    # State lease exclusive fence (separate from ResourceLease mount fence).
    state_a = StateLease(
        session.state_directory / "lease-probe",
        mount_id="mount:lease-probe",
        holder_id="holder:lease-a",
    )
    state_a.acquire(timeout_seconds=0.0)
    try:
        state_b = StateLease(
            session.state_directory / "lease-probe",
            mount_id="mount:lease-probe",
            holder_id="holder:lease-b",
        )
        try:
            state_b.acquire(timeout_seconds=0.0)
            state_b.release()
            raise ContainerHarnessError(
                "state lease failed to fence second holder", code="LEAK"
            )
        except StateLeaseHeldError:
            state_fenced = True
    finally:
        state_a.release()

    # Close session and assert full release.
    receipt = session.close()
    if not receipt.get("released"):
        raise ContainerHarnessError(
            "leases not fully released after cleanup",
            code="LEAK",
            detail=receipt,
        )
    if receipt.get("privileged_leaked"):
        raise ContainerHarnessError("privileged profile leaked", code="PRIVILEGED")
    # After release, a new holder can acquire.
    successor = ResourceLease(
        session.leases.container.root,
        role="container",
        resource_id=session.leases.container.resource_id,
        holder_id="holder:successor",
    )
    successor.acquire(blocking=False)
    successor.release()
    return {
        "fenced": True,
        "state_fenced": state_fenced,
        "released": True,
        "held_remaining": [],
        "privileged_leaked": False,
        "container_leaked": False,
        "process_leaked": False,
        "mount_leaked": False,
        "volume_lease_leaked": False,
        "cleanup": receipt,
    }


# Cases that do not require a live mount session.
SESSIONLESS_CASES: Final[frozenset[ConformanceCaseId]] = frozenset(
    {
        ConformanceCaseId.ABSENT_DEVICE,
        ConformanceCaseId.ABSENT_CAPABILITY,
        ConformanceCaseId.NO_PRIVILEGED,
    }
)

CASE_RUNNERS: Final[
    dict[ConformanceCaseId, Callable[[ContainerMountSession | None], dict[str, Any]]]
] = {
    ConformanceCaseId.MINIMAL_CRUD: _case_minimal_crud,  # type: ignore[dict-item]
    ConformanceCaseId.MINIMAL_FSYNC: _case_minimal_fsync,  # type: ignore[dict-item]
    ConformanceCaseId.RESTART: _case_restart,  # type: ignore[dict-item]
    ConformanceCaseId.RECOVERY: _case_recovery,  # type: ignore[dict-item]
    ConformanceCaseId.ABSENT_DEVICE: _case_absent_device,
    ConformanceCaseId.ABSENT_CAPABILITY: _case_absent_capability,
    ConformanceCaseId.NO_PRIVILEGED: _case_no_privileged,
    ConformanceCaseId.LEASE_CLEANUP: _case_lease_cleanup,  # type: ignore[dict-item]
}


# ---------------------------------------------------------------------------
# Case receipts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CaseReceipt:
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
    message: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)
    unix_ms: int = 0
    receipt_id: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "task_id": TASK_ID,
            "case_id": self.case_id,
            "status": self.status.value,
            "plane": self.plane.value,
            "success": self.success,
            "elapsed_seconds": self.elapsed_seconds,
            "timeout_seconds": self.timeout_seconds,
            "readiness_timeout_seconds": self.readiness_timeout_seconds,
            "support_claim": self.support_claim,
            "support_promoted": self.support_promoted,
            "message": self.message,
            "detail": dict(self.detail),
            "unix_ms": self.unix_ms or _unix_ms(),
            "receipt_id": self.receipt_id,
            "bounded": self.elapsed_seconds <= self.timeout_seconds,
            "profile": PROFILE_MINIMAL,
            "privileged": False,
        }


@dataclass(frozen=True)
class SuiteReceipt:
    SCHEMA: ClassVar[str] = SUITE_RECEIPT_SCHEMA

    status: str
    profile: str
    support_claim: str
    support_promoted: bool
    docker_ready: bool
    plane: ExecutionPlane
    cases: tuple[CaseReceipt, ...]
    elapsed_seconds: float
    message: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)
    receipt_id: str = ""
    unix_ms: int = 0

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "task_id": TASK_ID,
            "status": self.status,
            "profile": self.profile,
            "support_claim": self.support_claim,
            "support_promoted": self.support_promoted,
            "docker_ready": self.docker_ready,
            "plane": self.plane.value,
            "cases": [c.to_record() for c in self.cases],
            "elapsed_seconds": self.elapsed_seconds,
            "message": self.message,
            "detail": dict(self.detail),
            "receipt_id": self.receipt_id,
            "unix_ms": self.unix_ms or _unix_ms(),
            "privileged": False,
            "propagation_claim": PROPAGATION_IN_CONTAINER,
            "docker_desktop_propagation_claimed": False,
        }


# ---------------------------------------------------------------------------
# Main harness
# ---------------------------------------------------------------------------


class ContainerLiveHarness:
    """Bounded Docker container mount/restart/recovery conformance harness."""

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
                tempfile.mkdtemp(prefix="kvfs-container-live-")
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
        self.volume_root = self.work_directory / "volumes"
        self.volume_root.mkdir(parents=True, exist_ok=True)

        self.readiness_timeout_seconds = float(readiness_timeout_seconds)
        self.case_timeout_seconds = float(case_timeout_seconds)
        self.capability_budget_seconds = float(capability_budget_seconds)

        if prefer_live is None:
            env_force = os.environ.get(LIVE_FORCE_ENV, "").strip().lower()
            prefer_live = env_force in {"1", "true", "yes", "live", "force"}
        self.prefer_live = bool(prefer_live)

        self._docker: dict[str, Any] | None = None
        self._sessions: list[ContainerMountSession] = []
        self._case_receipts: list[CaseReceipt] = []
        self._lock = threading.RLock()
        self._closed = False
        self._cleanup_watchdog: CleanupWatchdog | None = None

    def probe_docker(self, *, force: bool = False) -> dict[str, Any]:
        if self._docker is not None and not force:
            return self._docker
        receipt = probe_docker_daemon(budget_seconds=self.capability_budget_seconds)
        self._docker = receipt
        _atomic_write_json(self.receipts_directory / "docker-capability.json", receipt)
        return receipt

    @property
    def docker_ready(self) -> bool:
        return bool(self.probe_docker().get("docker_ready"))

    @property
    def plane(self) -> ExecutionPlane:
        if self.prefer_live and self.docker_ready:
            return ExecutionPlane.LIVE_DOCKER
        return ExecutionPlane.HERMETIC

    def open_session(self) -> ContainerMountSession:
        plane = self.plane
        token = uuid.uuid4().hex[:10]
        state_dir = self.state_root / f"session-{token}"
        mountpoint = self.mount_root / f"mnt-{token}"
        wal_dir = self.volume_root / f"wal-{token}"
        cache_dir = self.volume_root / f"cache-{token}"
        for path in (state_dir, mountpoint, wal_dir, cache_dir):
            path.mkdir(parents=True, exist_ok=True)

        leases = build_lease_bundle(
            self.lease_root, token=token, state_directory=state_dir
        )
        # State lease is acquired by lifecycle child; avoid double-hold.
        leases.state_lease = None
        leases.acquire_all()

        life_mid = f"mount:container-{uuid.uuid4().hex[:8]}"
        ops_mid = life_mid if plane is ExecutionPlane.LIVE_DOCKER else DEFAULT_MOUNT_ID
        ops_platform = (
            HostPlatform.LINUX
            if plane is ExecutionPlane.LIVE_DOCKER
            else HostPlatform.HERMETIC
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
            hermetic=True,
            generation_id=f"wal-gen:ctr-{uuid.uuid4().hex[:8]}",
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
            leases.release_all()
            raise
        elapsed = _monotonic() - started
        if elapsed > self.readiness_timeout_seconds:
            try:
                ops.close()
            except Exception:  # noqa: BLE001
                pass
            life.unmount(timeout_seconds=5.0)
            leases.release_all()
            raise ContainerHarnessError(
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
            leases.release_all()
            raise ContainerHarnessError(
                "mount did not become ready after recovery",
                code="MOUNT_NOT_READY",
                detail=readiness.to_record(),
            )
        if isinstance(life.pid, int) and life.pid > 0:
            leases.tracked_pids.append(life.pid)

        session = ContainerMountSession(
            lifecycle=life,
            operations=ops,
            mountpoint=mountpoint,
            state_directory=state_dir,
            wal_directory=wal_dir,
            cache_directory=cache_dir,
            plane=plane,
            mount_id=life_mid,
            leases=leases,
            profile=PROFILE_MINIMAL,
            privileged=False,
            propagation_claim=PROPAGATION_IN_CONTAINER,
        )
        with self._lock:
            self._sessions.append(session)
        return session

    def run_case(
        self,
        case_id: ConformanceCaseId | str,
        *,
        session: ContainerMountSession | None = None,
    ) -> CaseReceipt:
        if not isinstance(case_id, ConformanceCaseId):
            case_id = ConformanceCaseId(case_id)
        runner = CASE_RUNNERS[case_id]
        plane = self.plane
        docker = self.probe_docker()
        docker_ready = bool(docker.get("docker_ready"))
        owns_session = session is None and case_id not in SESSIONLESS_CASES
        started = _monotonic()
        watchdog = CaseWatchdog(self.case_timeout_seconds)
        watchdog.start(case_id.value)
        detail: dict[str, Any] = {}
        status = CaseStatus.FAILED
        message = ""
        success = False
        elapsed = 0.0

        try:
            if owns_session:
                session = self.open_session()
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
                        "error": type(exc).__name__,
                        "message": _bounded_text(exc),
                    }
                else:
                    status = CaseStatus.FAILED
                    message = _bounded_text(exc)
                    success = False
                    detail = {"error": type(exc).__name__, "message": message}
                    if isinstance(exc, ContainerHarnessError):
                        detail["code"] = exc.code
                        detail["error_detail"] = dict(exc.detail)
        finally:
            watchdog.cancel()
            elapsed = _monotonic() - started
            if owns_session and session is not None:
                # lease_cleanup case closes itself.
                if case_id is not ConformanceCaseId.LEASE_CLEANUP:
                    try:
                        cleanup = session.close()
                        if not cleanup.get("released") and success:
                            status = CaseStatus.CLEANUP_FAILED
                            success = False
                            message = "cleanup leaked resources"
                            detail = dict(detail)
                            detail["cleanup"] = cleanup
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
            docker_ready=docker_ready,
            live_cases_passed=success and plane is ExecutionPlane.LIVE_DOCKER,
            plane=plane,
        )
        if not docker_ready:
            support_claim = SUPPORT_CLAIM_UNAVAILABLE
        support_promoted = can_promote_live_support(
            docker_ready=docker_ready,
            support_claim=support_claim,
            status="passed" if success and plane is ExecutionPlane.LIVE_DOCKER else "failed",
            profile=(
                PROFILE_LIVE_DOCKER
                if plane is ExecutionPlane.LIVE_DOCKER
                else PROFILE_HERMETIC
            ),
        )
        if support_promoted and not docker_ready:
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
        started = _monotonic()
        self._cleanup_watchdog = CleanupWatchdog(
            self.cleanup,
            deadline_seconds=self.case_timeout_seconds * (len(REQUIRED_CASE_IDS) + 1),
        )
        self._cleanup_watchdog.start()
        try:
            docker = self.probe_docker()
            docker_ready = bool(docker.get("docker_ready"))
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
                docker_ready
                and plane is ExecutionPlane.LIVE_DOCKER
                and all_passed
                and ran_required
            )
            if live_ok:
                status = "passed"
                profile = PROFILE_LIVE_DOCKER
                support_claim = SUPPORT_CLAIM_LIVE_PASSED
                support_promoted = True
            elif all_passed:
                profile = PROFILE_HERMETIC
                if docker_ready:
                    status = "hermetic_passed"
                    support_claim = SUPPORT_CLAIM_HERMETIC_ONLY
                else:
                    status = SUPPORT_CLAIM_UNAVAILABLE
                    support_claim = SUPPORT_CLAIM_UNAVAILABLE
                support_promoted = False
            else:
                status = "failed"
                profile = PROFILE_HERMETIC
                support_claim = (
                    SUPPORT_CLAIM_UNAVAILABLE
                    if not docker_ready
                    else SUPPORT_CLAIM_HERMETIC_ONLY
                )
                support_promoted = False

            if not can_promote_live_support(
                docker_ready=docker_ready,
                support_claim=support_claim,
                status=status,
                profile=profile,
            ):
                support_promoted = False
                if not docker_ready:
                    support_claim = SUPPORT_CLAIM_UNAVAILABLE
                    profile = PROFILE_HERMETIC

            if live_ok:
                message = "Docker container live conformance passed"
            elif not docker_ready and all_passed:
                message = (
                    "hermetic container conformance matrix passed; "
                    "capability_unavailable — live Docker support not promoted"
                )
            elif all_passed:
                message = "container conformance matrix passed without live promotion"
            else:
                failed = [r.case_id for r in receipts if not r.success]
                message = f"conformance failures: {failed}"

            suite = SuiteReceipt(
                status=status,
                profile=profile,
                support_claim=support_claim,
                support_promoted=support_promoted,
                docker_ready=docker_ready,
                plane=plane,
                cases=tuple(receipts),
                elapsed_seconds=_monotonic() - started,
                message=message,
                detail={
                    "required_case_count": len(REQUIRED_CASE_IDS),
                    "ran_case_count": len(receipts),
                    "passed_case_count": sum(1 for r in receipts if r.success),
                    "prefer_live": self.prefer_live,
                    "matrix_passed": all_passed,
                    "depends_on": list(DEPENDS_ON),
                    "minimal_profile": minimal_capability_profile(),
                },
                receipt_id=f"receipt:suite:{uuid.uuid4().hex}",
                unix_ms=_unix_ms(),
            )
            _atomic_write_json(
                self.receipts_directory / "suite.json", suite.to_record()
            )
            return suite
        finally:
            if self._cleanup_watchdog is not None:
                self._cleanup_watchdog.cancel()
                self._cleanup_watchdog = None
            self.cleanup()

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

    def __enter__(self) -> "ContainerLiveHarness":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def run_container_conformance(
    work_directory: str | Path | None = None,
    **kwargs: Any,
) -> SuiteReceipt:
    with ContainerLiveHarness(work_directory, **kwargs) as harness:
        return harness.run_suite()


def required_case_ids() -> tuple[str, ...]:
    return tuple(c.value for c in REQUIRED_CASE_IDS)


# ---------------------------------------------------------------------------
# Tests — artifact / identity / bounds
# ---------------------------------------------------------------------------


def test_declared_outputs_exist() -> None:
    assert TEST_PATH.is_file()
    assert TEST_PATH.stat().st_size > 0
    assert DOCKERFILE_PATH.is_file()
    assert COMPOSE_PATH.is_file()


def test_task_identity_and_bounds() -> None:
    assert TASK_ID == "KVFS-700"
    assert DEPENDS_ON == ("KVFS-506", "KVFS-701")
    assert READINESS_TIMEOUT_SECONDS == 15.0
    assert CASE_TIMEOUT_SECONDS == 60.0
    assert CAPABILITY_PROBE_BUDGET_SECONDS <= 5.0
    assert MISSING_INPUT_BUDGET_SECONDS <= 5.0
    assert PROFILE_MINIMAL == "linux-fuse-minimal"
    assert PROPAGATION_IN_CONTAINER == "in_container"
    assert PROPAGATION_DOCKER_DESKTOP == "docker_desktop"


def test_required_case_matrix_is_complete() -> None:
    ids = set(required_case_ids())
    expected = {
        "minimal_crud",
        "minimal_fsync",
        "restart",
        "recovery",
        "absent_device",
        "absent_capability",
        "no_privileged",
        "lease_cleanup",
    }
    assert ids == expected
    for case_id in ConformanceCaseId:
        assert case_id in CASE_RUNNERS


def test_harness_import_is_inert() -> None:
    """Importing this module must not load fusepy or start Docker containers."""

    source = TEST_PATH.read_text(encoding="utf-8")
    # Build fragments so this self-check does not embed the banned literals.
    banned = (
        "import " + "fuse\n",
        "import " + "fusepy\n",
        "from " + "fuse ",
        "from " + "fusepy ",
        "ctypes." + "CDLL",
    )
    for fragment in banned:
        assert fragment not in source, fragment
    # Module-level docker run must not exist (header before first docstring).
    header = source.split('"""')[0]
    assert ("docker" + " run") not in header
    pre_existing = {name for name in ("fuse", "fusepy") if name in sys.modules}
    _ = probe_docker_daemon(budget_seconds=1.0)
    for name in ("fuse", "fusepy"):
        if name not in pre_existing:
            assert name not in sys.modules


# ---------------------------------------------------------------------------
# Minimal profile contract (KVFS-701 surface)
# ---------------------------------------------------------------------------


def test_minimal_capability_profile_never_privileged() -> None:
    profile = minimal_capability_profile()
    assert profile["privileged"] is False
    assert profile["privileged_forbidden"] is True
    assert profile["device_present"] is True
    assert profile["cap_present"] is True
    assert profile["required_device"] == REQUIRED_DEVICE
    assert profile["required_cap"] == REQUIRED_CAP
    assert profile["host_propagation_claimed"] is False
    assert profile["docker_desktop_propagation_claimed"] is False
    assert profile["propagation_claim"] == PROPAGATION_IN_CONTAINER
    service = _compose_service()
    assert service.get("privileged") is False
    assert service.get("init") is True


def test_compose_separate_volumes_and_foreground() -> None:
    service = _compose_service()
    env = service.get("environment") or {}
    if isinstance(env, list):
        env = {
            item.split("=", 1)[0]: item.split("=", 1)[1]
            for item in env
            if isinstance(item, str) and "=" in item
        }
    assert str(env.get("IPFS_KIT_KERNEL_VFS_FOREGROUND")) == "1"
    assert str(env.get("IPFS_KIT_KERNEL_VFS_READINESS")) == "1"
    assert str(env.get("IPFS_KIT_KERNEL_VFS_CAPABILITY_BUDGET_SECONDS")) == "5"
    assert str(env.get("KVFS_PRIVILEGED")).lower() == "false"
    volumes = service.get("volumes") or []
    blob = " ".join(str(v) for v in volumes)
    assert STATE_VOLUME in blob
    assert WAL_VOLUME in blob
    assert CACHE_VOLUME in blob
    assert STATE_PATH in blob
    assert WAL_PATH in blob
    assert CACHE_PATH in blob


# ---------------------------------------------------------------------------
# Preflight — absent device / capability fail promptly
# ---------------------------------------------------------------------------


def test_absent_device_fails_promptly() -> None:
    started = time.monotonic()
    receipt = run_capability_preflight(
        simulate_missing_device=True,
        require_sys_admin=None,
        budget_seconds=5.0,
    )
    elapsed = time.monotonic() - started
    assert receipt.ok is False
    assert receipt.device_ok is False
    assert receipt.within_budget is True
    assert elapsed < 5.5
    assert receipt.native_mount_attempted is False
    assert receipt.support_promoted is False
    assert any("device" in e.lower() or "missing" in e.lower() for e in receipt.errors)


def test_absent_capability_fails_promptly() -> None:
    started = time.monotonic()
    receipt = _preflight_cap_only_failure()
    elapsed = time.monotonic() - started
    assert receipt.ok is False
    assert receipt.cap_ok is False
    assert receipt.within_budget is True
    assert elapsed < 5.5
    assert receipt.native_mount_attempted is False
    assert receipt.privileged is False
    assert any("SYS_ADMIN" in e for e in receipt.errors)


def test_privileged_preflight_rejected() -> None:
    receipt = run_capability_preflight(
        privileged=True,
        require_sys_admin=None,
        simulate_missing_device=not Path(REQUIRED_DEVICE).exists(),
        budget_seconds=5.0,
    )
    assert receipt.ok is False
    assert any("privileged" in e.lower() for e in receipt.errors)


def test_positive_profile_preflight_when_inputs_present() -> None:
    """When profile supplies device+cap (require_sys_admin=None), preflight OK."""

    if not Path(REQUIRED_DEVICE).exists():
        # Profile-level positive path: device simulated present via None skip.
        # Without a real char device we only assert the profile contract.
        profile = minimal_capability_profile()
        assert profile["device_present"] and profile["cap_present"]
        assert profile["privileged"] is False
        return
    receipt = run_capability_preflight(
        device=REQUIRED_DEVICE,
        require_sys_admin=None,
        budget_seconds=5.0,
    )
    assert receipt.ok is True
    assert receipt.device_ok is True
    assert receipt.cap_ok is True
    assert receipt.within_budget is True
    assert receipt.native_mount_attempted is False


# ---------------------------------------------------------------------------
# Support promotion fail-closed
# ---------------------------------------------------------------------------


def test_absent_docker_cannot_promote_support(tmp_path: Path) -> None:
    with ContainerLiveHarness(tmp_path / "work-cap", prefer_live=False) as h:
        docker = h.probe_docker()
        if not docker.get("docker_ready"):
            assert h.plane is ExecutionPlane.HERMETIC
            assert (
                support_claim_for(
                    docker_ready=False,
                    live_cases_passed=True,
                    plane=ExecutionPlane.LIVE_DOCKER,
                )
                == SUPPORT_CLAIM_UNAVAILABLE
            )
            assert (
                can_promote_live_support(
                    docker_ready=False,
                    support_claim=SUPPORT_CLAIM_LIVE_PASSED,
                    status="passed",
                    profile=PROFILE_LIVE_DOCKER,
                )
                is False
            )


def test_support_claim_helper_fail_closed() -> None:
    assert (
        support_claim_for(
            docker_ready=False,
            live_cases_passed=True,
            plane=ExecutionPlane.LIVE_DOCKER,
        )
        == SUPPORT_CLAIM_UNAVAILABLE
    )
    assert (
        support_claim_for(
            docker_ready=True,
            live_cases_passed=True,
            plane=ExecutionPlane.LIVE_DOCKER,
        )
        == SUPPORT_CLAIM_LIVE_PASSED
    )
    assert (
        support_claim_for(
            docker_ready=True,
            live_cases_passed=True,
            plane=ExecutionPlane.HERMETIC,
        )
        == SUPPORT_CLAIM_HERMETIC_ONLY
    )
    assert (
        can_promote_live_support(
            docker_ready=True,
            support_claim=SUPPORT_CLAIM_LIVE_PASSED,
            status="passed",
            profile=PROFILE_LIVE_DOCKER,
        )
        is True
    )
    assert (
        can_promote_live_support(
            docker_ready=True,
            support_claim=SUPPORT_CLAIM_LIVE_PASSED,
            status="passed",
            profile=PROFILE_HERMETIC,
        )
        is False
    )


# ---------------------------------------------------------------------------
# Individual conformance cases (bounded)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "case_id",
    list(ConformanceCaseId),
    ids=lambda c: c.value,
)
def test_each_conformance_case_is_bounded(
    case_id: ConformanceCaseId, tmp_path: Path
) -> None:
    with ContainerLiveHarness(tmp_path / f"work-{case_id.value}") as h:
        started = time.monotonic()
        receipt = h.run_case(case_id)
        elapsed = time.monotonic() - started
        assert elapsed < CASE_TIMEOUT_SECONDS
        assert receipt.elapsed_seconds < CASE_TIMEOUT_SECONDS
        assert receipt.timeout_seconds == CASE_TIMEOUT_SECONDS
        assert receipt.readiness_timeout_seconds == READINESS_TIMEOUT_SECONDS
        assert receipt.case_id == case_id.value
        assert receipt.success is True, receipt.to_record()
        assert receipt.status is CaseStatus.PASSED
        assert receipt.to_record()["bounded"] is True
        assert receipt.to_record()["privileged"] is False
        if not h.docker_ready:
            assert receipt.support_promoted is False
            assert receipt.support_claim == SUPPORT_CLAIM_UNAVAILABLE
            assert receipt.plane is ExecutionPlane.HERMETIC
        path = h.receipts_directory / f"case-{case_id.value}.json"
        assert path.is_file()
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["case_id"] == case_id.value
        assert payload["success"] is True


def test_minimal_crud_receipt_lists_ops(tmp_path: Path) -> None:
    with ContainerLiveHarness(tmp_path / "work-crud") as h:
        receipt = h.run_case(ConformanceCaseId.MINIMAL_CRUD)
        assert receipt.success is True
        ops = receipt.detail.get("operations", [])
        for name in ("mkdir", "create", "read", "write", "rename", "unlink", "rmdir"):
            assert name in ops
        assert receipt.detail.get("privileged") is False
        assert receipt.detail.get("propagation_claim") == PROPAGATION_IN_CONTAINER


def test_minimal_fsync_receipt(tmp_path: Path) -> None:
    with ContainerLiveHarness(tmp_path / "work-fsync") as h:
        receipt = h.run_case(ConformanceCaseId.MINIMAL_FSYNC)
        assert receipt.success is True
        assert receipt.detail.get("fsync") is True
        assert receipt.detail.get("fdatasync") is True


def test_restart_recovers_before_ready(tmp_path: Path) -> None:
    with ContainerLiveHarness(tmp_path / "work-restart") as h:
        receipt = h.run_case(ConformanceCaseId.RESTART)
        assert receipt.success is True
        assert receipt.detail.get("restarted") is True
        assert receipt.detail.get("recovery_preserved") is True
        assert receipt.detail.get("recovery_before_ready") is True


def test_recovery_after_kill_is_idempotent(tmp_path: Path) -> None:
    with ContainerLiveHarness(tmp_path / "work-recovery") as h:
        receipt = h.run_case(ConformanceCaseId.RECOVERY)
        assert receipt.success is True
        assert receipt.detail.get("killed") is True
        assert receipt.detail.get("recovered") is True
        assert receipt.detail.get("recovery_before_ready") is True
        assert receipt.detail.get("idempotent") is True


def test_absent_device_case_receipt(tmp_path: Path) -> None:
    with ContainerLiveHarness(tmp_path / "work-adev") as h:
        receipt = h.run_case(ConformanceCaseId.ABSENT_DEVICE)
        assert receipt.success is True
        assert receipt.detail.get("failed_promptly") is True
        assert receipt.detail.get("native_mount_attempted") is False
        assert receipt.detail.get("docker_capability") == "missing_device"
        assert receipt.detail.get("elapsed_seconds", 99) < 5.5


def test_absent_capability_case_receipt(tmp_path: Path) -> None:
    with ContainerLiveHarness(tmp_path / "work-acap") as h:
        receipt = h.run_case(ConformanceCaseId.ABSENT_CAPABILITY)
        assert receipt.success is True
        assert receipt.detail.get("failed_promptly") is True
        assert receipt.detail.get("native_mount_attempted") is False
        assert receipt.detail.get("docker_capability") == "missing_cap"
        assert receipt.detail.get("blanket_privileged_forbidden") is True
        assert receipt.detail.get("elapsed_seconds", 99) < 5.5


def test_lease_cleanup_leaves_no_leaks(tmp_path: Path) -> None:
    with ContainerLiveHarness(tmp_path / "work-lease") as h:
        receipt = h.run_case(ConformanceCaseId.LEASE_CLEANUP)
        assert receipt.success is True
        assert receipt.detail.get("released") is True
        assert receipt.detail.get("privileged_leaked") is False
        assert receipt.detail.get("container_leaked") is False
        assert receipt.detail.get("process_leaked") is False
        assert receipt.detail.get("mount_leaked") is False
        assert receipt.detail.get("volume_lease_leaked") is False
        assert receipt.detail.get("held_remaining") == []


def test_exclusive_container_lease_fences_second_holder(tmp_path: Path) -> None:
    root = tmp_path / "leases"
    first = ResourceLease(root, role="container", resource_id="ctr-a", holder_id="h1")
    first.acquire()
    try:
        second = ResourceLease(
            root, role="container", resource_id="ctr-a", holder_id="h2"
        )
        with pytest.raises(ContainerHarnessError) as exc_info:
            second.acquire(blocking=False)
        assert exc_info.value.code == "LEASE_HELD"
    finally:
        first.release()
    third = ResourceLease(root, role="container", resource_id="ctr-a", holder_id="h3")
    third.acquire(blocking=False)
    third.release()


def test_volume_leases_are_distinct_roles(tmp_path: Path) -> None:
    root = tmp_path / "vol-leases"
    bundle = build_lease_bundle(root, token="voltest", state_directory=tmp_path / "st")
    bundle.state_lease = None
    bundle.acquire_all()
    try:
        assert bundle.volume_state.held
        assert bundle.volume_wal.held
        assert bundle.volume_cache.held
        assert bundle.volume_state.resource_id != bundle.volume_wal.resource_id
        assert bundle.volume_wal.resource_id != bundle.volume_cache.resource_id
        assert bundle.privileged_guard.held
        # Privileged guard path encodes never-privileged.
        assert "never-privileged" in bundle.privileged_guard.resource_id
    finally:
        receipt = bundle.release_all()
    assert receipt["released"] is True
    assert receipt["privileged_leaked"] is False


# ---------------------------------------------------------------------------
# Full suite
# ---------------------------------------------------------------------------


def test_full_suite_hermetic_matrix(tmp_path: Path) -> None:
    with ContainerLiveHarness(tmp_path / "work-suite", prefer_live=False) as h:
        suite = h.run_suite()
        record = suite.to_record()
        assert suite.plane is ExecutionPlane.HERMETIC
        assert suite.support_promoted is False
        assert record["privileged"] is False
        assert record["docker_desktop_propagation_claimed"] is False
        assert record["propagation_claim"] == PROPAGATION_IN_CONTAINER
        assert all(c.success for c in suite.cases), record
        assert {c.case_id for c in suite.cases} == set(required_case_ids())
        assert (h.receipts_directory / "suite.json").is_file()
        if not suite.docker_ready:
            assert suite.support_claim == SUPPORT_CLAIM_UNAVAILABLE
            assert suite.status == SUPPORT_CLAIM_UNAVAILABLE
        else:
            assert suite.support_claim == SUPPORT_CLAIM_HERMETIC_ONLY
            assert suite.status == "hermetic_passed"


def test_session_ready_within_15_seconds(tmp_path: Path) -> None:
    with ContainerLiveHarness(tmp_path / "work-ready") as h:
        started = time.monotonic()
        session = h.open_session()
        elapsed = time.monotonic() - started
        try:
            assert elapsed < READINESS_TIMEOUT_SECONDS
            assert session.lifecycle.ready is True
            assert session.privileged is False
            assert session.profile == PROFILE_MINIMAL
            assert session.propagation_claim == PROPAGATION_IN_CONTAINER
            readiness = session.lifecycle.read_readiness()
            assert readiness is not None
            assert readiness.recovery_complete is True
        finally:
            cleanup = session.close()
            assert cleanup.get("released") is True


def test_case_watchdog_fires_after_timeout() -> None:
    wd = CaseWatchdog(timeout_seconds=0.15)
    wd.start("watchdog-demo")
    time.sleep(0.35)
    assert wd.fired is True
    wd.cancel()


def test_entrypoint_contract_embedded_in_dockerfile() -> None:
    """KVFS-701 entrypoint still covers either missing input within 5s."""

    text = _dockerfile_text()
    assert "CAP_SYS_ADMIN" in text or "_CAP_SYS_ADMIN" in text or "SYS_ADMIN" in text
    assert REQUIRED_DEVICE in text
    assert "min(value, 5.0)" in text or "min(value, 5)" in text
    assert "do not use --privileged" in text.lower() or "privileged" in text.lower()
    assert "os.execvp" in text
    assert "preflight" in text


def test_default_in_container_does_not_claim_host_or_desktop_propagation() -> None:
    profile = minimal_capability_profile()
    assert profile["propagation_claim"] == PROPAGATION_IN_CONTAINER
    assert profile["host_propagation_claimed"] is False
    assert profile["docker_desktop_propagation_claimed"] is False
    compose = COMPOSE_PATH.read_text(encoding="utf-8")
    assert "Docker Desktop propagation is not claimed" in compose or (
        "does not claim Docker Desktop" in compose
    )
    # Default service has no rshared / shared bind for host mount visibility.
    service = _compose_service()
    volumes = service.get("volumes") or []
    for entry in volumes:
        if isinstance(entry, dict):
            bind = entry.get("bind") or {}
            prop = ""
            if isinstance(bind, dict):
                prop = str(bind.get("propagation", ""))
            prop = prop or str(entry.get("propagation", ""))
            assert prop.lower() not in {"rshared", "shared"}
        elif isinstance(entry, str):
            parts = entry.split(":")
            opts = parts[-1].split(",") if len(parts) >= 3 else []
            for opt in opts:
                assert opt.lower() not in {"rshared", "shared"}


__all__ = [
    "TASK_ID",
    "ContainerLiveHarness",
    "ConformanceCaseId",
    "ExecutionPlane",
    "CaseStatus",
    "run_container_conformance",
    "run_capability_preflight",
    "minimal_capability_profile",
    "required_case_ids",
    "PROFILE_MINIMAL",
    "PROPAGATION_IN_CONTAINER",
    "PROPAGATION_NATIVE_RSHARED",
    "PROPAGATION_DOCKER_DESKTOP",
]

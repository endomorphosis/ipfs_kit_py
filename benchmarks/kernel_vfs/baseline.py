#!/usr/bin/env python3
"""KVFS-108: bounded platform doctor and hermetic performance baselines.

Probe-only: does not install drivers, mount filesystems, optimize production
paths, or import fusepy/WinFsp (native loaders stay inert). Missing capability
is a typed actionable receipt, never an unbounded wait.

Usage:
  python benchmarks/kernel_vfs/baseline.py --check-schema
  python benchmarks/kernel_vfs/baseline.py --run-doctor
  python benchmarks/kernel_vfs/baseline.py --run
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import random
import shutil
import statistics
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

SCHEMA = "KernelVFSBaselineManifest@1"
SCHEMA_VERSION = "ipfs_kit_py.kernel_vfs.baseline@1"
DOCTOR_SCHEMA = "KernelVFSDoctorReport@1"
TASK_ID = "KVFS-108"
DOCTOR_BUDGET_SECONDS = 5.0

HERE = Path(__file__).resolve().parent
PACKAGE_ROOT = HERE.parents[1]
WORKLOADS_PATH = HERE / "workloads.json"

REQUIRED_DOCTOR_CHECKS: Tuple[str, ...] = (
    "os_architecture",
    "python_binding",
    "native_abi",
    "device_driver_service",
    "helper",
    "mountpoint_state_permissions",
    "docker_capability",
    "actionable_absence",
)

REQUIRED_BASELINE_OBSERVATIONS: Tuple[str, ...] = (
    "sequential_io",
    "random_io",
    "metadata",
    "memory",
    "handles",
    "wal",
    "arc",
)

REQUIRED_IDENTITY_FIELDS: Tuple[str, ...] = (
    "hardware",
    "os",
    "python",
    "revision",
    "dataset",
    "seed",
    "concurrency",
    "durability",
    "warmup",
    "samples",
    "confidence",
)


class BaselineSchemaError(ValueError):
    """Raised when kernel VFS baseline artifacts fail schema checks."""


class DoctorBudgetError(RuntimeError):
    """Raised when the platform doctor exceeds its hard time budget."""


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_json(obj: Any) -> str:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return _sha256_bytes(payload.encode("utf-8"))


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _percentile(sorted_values: Sequence[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    if pct <= 0:
        return float(sorted_values[0])
    if pct >= 100:
        return float(sorted_values[-1])
    k = (len(sorted_values) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return float(sorted_values[f])
    return float(sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f))


def _latency_stats(samples_ms: Sequence[float]) -> Dict[str, float]:
    ordered = sorted(float(x) for x in samples_ms)
    return {
        "n": float(len(ordered)),
        "mean_ms": float(statistics.fmean(ordered)) if ordered else 0.0,
        "p50_ms": _percentile(ordered, 50),
        "p95_ms": _percentile(ordered, 95),
        "p99_ms": _percentile(ordered, 99),
    }


def load_workloads() -> Dict[str, Any]:
    if not WORKLOADS_PATH.is_file():
        raise BaselineSchemaError(f"missing workloads artifact: {WORKLOADS_PATH}")
    doc = _read_json(WORKLOADS_PATH)
    if not isinstance(doc, dict):
        raise BaselineSchemaError("workloads.json must be a JSON object")
    return doc


# ---------------------------------------------------------------------------
# Environment capture
# ---------------------------------------------------------------------------


def capture_hardware() -> Dict[str, Any]:
    return {
        "machine": platform.machine(),
        "processor": platform.processor() or "unknown",
        "cpu_count_logical": os.cpu_count(),
        "platform_node_hash": _sha256_bytes(platform.node().encode("utf-8"))[:16],
    }


def capture_os() -> Dict[str, Any]:
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "platform": platform.platform(),
        "architecture": platform.architecture()[0],
    }


def capture_python() -> Dict[str, Any]:
    return {
        "version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "executable": sys.executable,
        "version_info": list(sys.version_info[:3]),
    }


def capture_revision(package_root: Path = PACKAGE_ROOT) -> Dict[str, Any]:
    rev: Dict[str, Any] = {
        "package_root": str(package_root),
        "git_commit": None,
        "dirty": None,
        "source": "unavailable",
    }
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(package_root),
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        ).strip()
        dirty_out = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=str(package_root),
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
        rev["git_commit"] = commit
        rev["dirty"] = bool(dirty_out.strip())
        rev["source"] = "git"
    except Exception as exc:  # pragma: no cover - environment dependent
        rev["error"] = type(exc).__name__
    return rev


def build_identity(
    *,
    profile: Mapping[str, Any],
    seed: int,
    package_root: Path = PACKAGE_ROOT,
    dataset: str = "dataset:kernel_vfs_baseline_v1",
) -> Dict[str, Any]:
    identity = {
        "hardware": capture_hardware(),
        "os": capture_os(),
        "python": capture_python(),
        "revision": capture_revision(package_root),
        "dataset": dataset,
        "seed": seed,
        "concurrency": int(profile.get("default_concurrency", 1)),
        "durability": str(profile.get("default_durability", "memory_sync")),
        "warmup": int(profile.get("warmup_samples", 3)),
        "samples": int(profile.get("measurement_samples", 12)),
        "confidence": float(profile.get("confidence_level", 0.95)),
        "profile_defaults": {
            "backend_tier": profile.get("backend_tier"),
            "storage": profile.get("storage"),
            "daemon": profile.get("daemon"),
            "networked": profile.get("networked"),
            "native_mount": profile.get("native_mount", False),
        },
    }
    identity["identity_digest"] = _sha256_json(
        {k: identity[k] for k in REQUIRED_IDENTITY_FIELDS}
    )
    return identity


# ---------------------------------------------------------------------------
# Platform doctor (bounded, no mount, no fusepy import)
# ---------------------------------------------------------------------------


def _probe_python_binding() -> Dict[str, Any]:
    """Record fusepy *presence* without importing (import loads native libs)."""
    spec = importlib.util.find_spec("fusepy")
    fuse_spec = importlib.util.find_spec("fuse")
    present = spec is not None or fuse_spec is not None
    return {
        "check": "python_binding",
        "available": present,
        "fusepy_find_spec": spec is not None,
        "fuse_module_find_spec": fuse_spec is not None,
        "imported": False,
        "note": "find_spec only; import is deferred because fusepy loads native code",
        "actionable_absence": None
        if present
        else (
            "Install the optional [fuse] extra (fusepy) for Linux host mounts. "
            "Package import success alone does not establish native FUSE capability."
        ),
    }


def _probe_native_abi(system: str) -> Dict[str, Any]:
    candidates: List[str] = []
    found: List[str] = []
    if system == "Linux":
        candidates = [
            "/usr/lib/x86_64-linux-gnu/libfuse.so.2",
            "/usr/lib/x86_64-linux-gnu/libfuse3.so.3",
            "/usr/lib/aarch64-linux-gnu/libfuse.so.2",
            "/usr/lib/aarch64-linux-gnu/libfuse3.so.3",
            "/usr/lib64/libfuse.so.2",
            "/usr/lib64/libfuse3.so.3",
            "/lib/x86_64-linux-gnu/libfuse.so.2",
            "/lib/x86_64-linux-gnu/libfuse3.so.3",
        ]
        for path in candidates:
            if os.path.exists(path):
                found.append(path)
        # ctypes.util.find_library does not dlopen the library.
        try:
            import ctypes.util

            for name in ("fuse", "fuse3"):
                resolved = ctypes.util.find_library(name)
                if resolved and resolved not in found:
                    found.append(resolved)
        except Exception as exc:  # pragma: no cover
            return {
                "check": "native_abi",
                "available": bool(found),
                "system": system,
                "candidates_checked": candidates,
                "found": found,
                "error": type(exc).__name__,
                "actionable_absence": None
                if found
                else "Install libfuse2 (FUSE 2.x ABI) for the supported Linux profile.",
            }
    elif system == "Windows":
        # WinFsp DLL presence is checked under device_driver_service.
        return {
            "check": "native_abi",
            "available": None,
            "system": system,
            "note": "Windows ABI is resolved via WinFsp DLL/service checks",
            "actionable_absence": None,
        }
    else:
        return {
            "check": "native_abi",
            "available": False,
            "system": system,
            "note": "unsupported host OS for kernel VFS mounts",
            "actionable_absence": (
                f"OS {system!r} is outside the supported Linux/Windows mount profiles."
            ),
        }

    return {
        "check": "native_abi",
        "available": bool(found),
        "system": system,
        "abi_family": "fuse2_or_fuse3" if found else None,
        "candidates_checked_count": len(candidates),
        "found": found,
        "actionable_absence": None
        if found
        else (
            "Install libfuse2 compatibility libraries for the supported Linux "
            "fusepy high-level FUSE 2.x ABI profile."
        ),
    }


def _probe_device_driver_service(system: str) -> Dict[str, Any]:
    if system == "Linux":
        dev_fuse = "/dev/fuse"
        exists = os.path.exists(dev_fuse)
        accessible = False
        if exists:
            accessible = os.access(dev_fuse, os.R_OK | os.W_OK)
        return {
            "check": "device_driver_service",
            "available": exists,
            "system": system,
            "device": dev_fuse,
            "exists": exists,
            "accessible": accessible,
            "actionable_absence": None
            if exists
            else (
                "Kernel FUSE device /dev/fuse is missing. Load the fuse module "
                "(e.g. modprobe fuse) or use a host/container profile that exposes it. "
                "This probe does not mount."
            ),
        }

    if system == "Windows":
        # Registry probe without starting WinFsp.
        install_dir = None
        service_hint = None
        try:
            import winreg  # type: ignore

            for root, sub in (
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WinFsp"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\WinFsp"),
            ):
                try:
                    with winreg.OpenKey(root, sub) as key:
                        install_dir, _ = winreg.QueryValueEx(key, "InstallDir")
                        break
                except OSError:
                    continue
        except Exception as exc:
            return {
                "check": "device_driver_service",
                "available": False,
                "system": system,
                "error": type(exc).__name__,
                "actionable_absence": (
                    "WinFsp registry lookup failed. Install a matching WinFsp "
                    "release; do not start the service from this doctor."
                ),
            }
        available = bool(install_dir)
        return {
            "check": "device_driver_service",
            "available": available,
            "system": system,
            "winfsp_install_dir": install_dir,
            "service_started": False,
            "service_hint": service_hint,
            "actionable_absence": None
            if available
            else (
                "WinFsp is not installed (registry InstallDir missing). "
                "Install WinFsp for the matching architecture; this doctor "
                "never starts the driver/service."
            ),
        }

    return {
        "check": "device_driver_service",
        "available": False,
        "system": system,
        "actionable_absence": f"No kernel device/driver profile for OS {system!r}.",
    }


def _probe_helper(system: str) -> Dict[str, Any]:
    helpers: List[str] = []
    if system == "Linux":
        for name in ("fusermount3", "fusermount"):
            path = shutil.which(name)
            if path:
                helpers.append(path)
        return {
            "check": "helper",
            "available": bool(helpers),
            "helpers": helpers,
            "actionable_absence": None
            if helpers
            else (
                "Neither fusermount3 nor fusermount is on PATH. Install fuse3/fuse "
                "userspace helpers. This probe does not invoke mount helpers."
            ),
        }
    if system == "Windows":
        return {
            "check": "helper",
            "available": None,
            "note": "WinFsp supplies the mount helper surface; no fusermount equivalent",
            "actionable_absence": None,
        }
    return {
        "check": "helper",
        "available": False,
        "actionable_absence": f"No mount helper profile for OS {system!r}.",
    }


def _probe_mountpoint_state_permissions() -> Dict[str, Any]:
    """Create disposable mountpoint/state dirs and record permission separation."""
    base = Path(tempfile.mkdtemp(prefix="kvfs108-doctor-"))
    mountpoint = base / "mnt"
    state_dir = base / "state"
    try:
        mountpoint.mkdir(mode=0o755)
        state_dir.mkdir(mode=0o700)
        mount_ok = os.access(mountpoint, os.R_OK | os.W_OK | os.X_OK)
        state_ok = os.access(state_dir, os.R_OK | os.W_OK | os.X_OK)
        same_path = mountpoint.resolve() == state_dir.resolve()
        return {
            "check": "mountpoint_state_permissions",
            "available": mount_ok and state_ok and not same_path,
            "mountpoint": str(mountpoint),
            "state_dir": str(state_dir),
            "mountpoint_accessible": mount_ok,
            "state_accessible": state_ok,
            "separated": not same_path,
            "mounted": False,
            "actionable_absence": None
            if (mount_ok and state_ok and not same_path)
            else (
                "Mountpoint and state directories must be writable and distinct. "
                "Never co-locate recovery state on the mountpoint."
            ),
        }
    finally:
        shutil.rmtree(base, ignore_errors=True)


def _probe_docker_capability() -> Dict[str, Any]:
    docker_bin = shutil.which("docker")
    socket_paths = [
        os.environ.get("DOCKER_HOST", ""),
        "unix:///var/run/docker.sock",
        "/var/run/docker.sock",
    ]
    socket_present = False
    socket_found: Optional[str] = None
    for raw in socket_paths:
        if not raw:
            continue
        path = raw
        if path.startswith("unix://"):
            path = path[len("unix://") :]
        if path.startswith("unix:"):
            path = path[len("unix:") :]
        if path.startswith("/") and os.path.exists(path):
            socket_present = True
            socket_found = path
            break

    # Capability is "docker tooling visible", not "FUSE inside docker works".
    available = bool(docker_bin) or socket_present
    return {
        "check": "docker_capability",
        "available": available,
        "docker_binary": docker_bin,
        "socket_present": socket_present,
        "socket_path": socket_found,
        "invoked_docker": False,
        "privileged_profile_forbidden": True,
        "required_profile_hint": {
            "device": "/dev/fuse",
            "cap_add": ["SYS_ADMIN"],
            "forbidden": ["--privileged"],
        },
        "actionable_absence": None
        if available
        else (
            "Docker CLI/socket not visible in this environment. Container FUSE "
            "claims require a dedicated profile with --device /dev/fuse and "
            "--cap-add SYS_ADMIN; blanket --privileged is forbidden."
        ),
    }


def run_doctor(*, budget_seconds: float = DOCTOR_BUDGET_SECONDS) -> Dict[str, Any]:
    """Run the bounded platform doctor and return a KernelVFSDoctorReport@1."""
    started = time.perf_counter()
    system = platform.system()
    machine = platform.machine()

    checks: Dict[str, Any] = {}
    checks["os_architecture"] = {
        "check": "os_architecture",
        "available": True,
        "os": system,
        "architecture": machine,
        "python_bits": platform.architecture()[0],
        "platform": platform.platform(),
        "actionable_absence": None,
    }
    checks["python_binding"] = _probe_python_binding()
    checks["native_abi"] = _probe_native_abi(system)
    checks["device_driver_service"] = _probe_device_driver_service(system)
    checks["helper"] = _probe_helper(system)
    checks["mountpoint_state_permissions"] = _probe_mountpoint_state_permissions()
    checks["docker_capability"] = _probe_docker_capability()

    absences = []
    for name in REQUIRED_DOCTOR_CHECKS:
        if name == "actionable_absence":
            continue
        entry = checks.get(name) or {}
        msg = entry.get("actionable_absence")
        if msg:
            absences.append({"check": name, "message": msg})

    checks["actionable_absence"] = {
        "check": "actionable_absence",
        "available": True,
        "count": len(absences),
        "items": absences,
        "policy": (
            "Missing native capability is a typed terminal receipt for this run; "
            "it never leaves a probe running and never claims support from import alone."
        ),
    }

    elapsed = time.perf_counter() - started
    if elapsed > budget_seconds:
        raise DoctorBudgetError(
            f"doctor exceeded budget: {elapsed:.3f}s > {budget_seconds:.3f}s"
        )

    native_ready = all(
        bool(checks[k].get("available"))
        for k in ("python_binding", "native_abi", "device_driver_service", "helper")
        if checks[k].get("available") is not None
    )

    report = {
        "schema": DOCTOR_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "elapsed_seconds": elapsed,
        "budget_seconds": budget_seconds,
        "within_budget": elapsed <= budget_seconds,
        "mounted": False,
        "native_capability_ready": native_ready,
        "support_claim": "capability_unavailable" if not native_ready else "probe_passed",
        "checks": checks,
        "required_checks": list(REQUIRED_DOCTOR_CHECKS),
        "policy": {
            "no_mount": True,
            "no_driver_install": True,
            "no_fusepy_import": True,
            "import_is_not_capability": True,
            "budget_seconds": budget_seconds,
        },
    }
    report["report_digest"] = _sha256_json(
        {
            "schema": report["schema"],
            "task_id": report["task_id"],
            "support_claim": report["support_claim"],
            "checks": {
                k: {
                    "available": v.get("available"),
                    "actionable_absence": v.get("actionable_absence"),
                }
                for k, v in checks.items()
            },
        }
    )
    return report


# ---------------------------------------------------------------------------
# Hermetic baseline measurements (no native mount)
# ---------------------------------------------------------------------------


def _measure_block_io(
    *,
    seed: int,
    samples: int,
    warmup: int,
    payload_bytes: int,
    sequential: bool,
    path_class: str,
) -> Dict[str, Any]:
    rng = random.Random(seed + (0 if sequential else 1) + (0 if path_class == "cold" else 17))
    region = bytearray(payload_bytes * max(samples, 8))
    block = bytes(rng.getrandbits(8) for _ in range(payload_bytes))
    latencies: List[float] = []

    def _one(i: int) -> None:
        if sequential:
            offset = (i * payload_bytes) % max(len(region) - payload_bytes, 1)
        else:
            offset = rng.randrange(0, max(len(region) - payload_bytes, 1))
        t0 = time.perf_counter()
        region[offset : offset + payload_bytes] = block
        _ = bytes(region[offset : offset + payload_bytes])
        latencies.append((time.perf_counter() - t0) * 1000.0)

    for i in range(warmup):
        _one(i)
    if path_class == "cold":
        # Drop warm effects for cold path: re-seed region and clear samples.
        region[:] = b"\x00" * len(region)
        latencies.clear()
        for i in range(warmup):
            _one(i)

    measure_start = time.perf_counter()
    for i in range(samples):
        _one(warmup + i)
    wall = time.perf_counter() - measure_start
    total_bytes = samples * payload_bytes
    stats = _latency_stats(latencies[-samples:] if latencies else [])
    return {
        "path_class": path_class,
        "mode": "sequential" if sequential else "random",
        "payload_bytes": payload_bytes,
        "samples": samples,
        "wall_seconds": wall,
        "throughput_mib_s": (total_bytes / (1024 * 1024) / wall) if wall > 0 else 0.0,
        "ops_per_s": (samples / wall) if wall > 0 else 0.0,
        **stats,
    }


def _measure_metadata(*, seed: int, samples: int, warmup: int, path_class: str) -> Dict[str, Any]:
    rng = random.Random(seed + 3)
    tree: Dict[str, Dict[str, Any]] = {}
    latencies: List[float] = []

    def _one(i: int) -> None:
        name = f"n{i % 64}"
        t0 = time.perf_counter()
        tree[name] = {"mode": 0o644, "size": i, "gen": i}
        _ = tree.get(name)
        if i % 4 == 0 and name in tree:
            tree[f"r{name}"] = tree.pop(name)
        if i % 7 == 0:
            tree.pop(f"r{name}", None)
            tree.pop(name, None)
        latencies.append((time.perf_counter() - t0) * 1000.0)
        _ = rng.random()

    for i in range(warmup):
        _one(i)
    if path_class == "cold":
        tree.clear()
        latencies.clear()
        for i in range(warmup):
            _one(i)

    measure_start = time.perf_counter()
    for i in range(samples):
        _one(warmup + i)
    wall = time.perf_counter() - measure_start
    stats = _latency_stats(latencies[-samples:] if latencies else [])
    return {
        "path_class": path_class,
        "samples": samples,
        "ops_per_s": (samples / wall) if wall > 0 else 0.0,
        "entries_remaining": len(tree),
        **stats,
    }


def _measure_memory() -> Dict[str, Any]:
    snap: Dict[str, Any] = {
        "pid": os.getpid(),
        "rss_bytes": None,
        "working_set_bytes": None,
    }
    # Synthetic working set (bounded) for hermetic observation shape.
    blob = bytearray(256 * 1024)
    for i in range(0, len(blob), 4096):
        blob[i] = i & 0xFF
    snap["working_set_bytes"] = len(blob)
    try:
        # Prefer resource module (stdlib) over optional psutil.
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF)
        # ru_maxrss is KiB on Linux, bytes on macOS.
        rss = int(usage.ru_maxrss)
        if platform.system() == "Linux":
            rss *= 1024
        snap["rss_bytes"] = rss
    except Exception as exc:  # pragma: no cover
        snap["error"] = type(exc).__name__
    # Keep reference so working set is not optimized away.
    snap["working_set_fingerprint"] = _sha256_bytes(bytes(blob[:64]))[:16]
    return snap


def _measure_handles(*, seed: int, samples: int, path_class: str) -> Dict[str, Any]:
    rng = random.Random(seed + 5)
    table: Dict[int, Dict[str, Any]] = {}
    next_fd = 1
    open_lat: List[float] = []
    lookup_lat: List[float] = []
    for i in range(samples):
        t0 = time.perf_counter()
        fd = next_fd
        next_fd += 1
        table[fd] = {"path": f"/h/{i}", "flags": i & 0x3, "gen": i}
        open_lat.append((time.perf_counter() - t0) * 1000.0)
        if table:
            target = rng.choice(list(table.keys()))
            t1 = time.perf_counter()
            _ = table.get(target)
            lookup_lat.append((time.perf_counter() - t1) * 1000.0)
        if path_class == "warm" and len(table) > samples // 2:
            table.pop(min(table), None)
    release_start = time.perf_counter()
    released = len(table)
    table.clear()
    release_wall = time.perf_counter() - release_start
    return {
        "path_class": path_class,
        "open_handles_peak": next_fd - 1,
        "open_handles": 0,
        "released": released,
        "lookup_p99_ms": _percentile(sorted(lookup_lat), 99) if lookup_lat else 0.0,
        "release_ops_per_s": (released / release_wall) if release_wall > 0 else 0.0,
        "open_p99_ms": _percentile(sorted(open_lat), 99) if open_lat else 0.0,
    }


def _measure_wal(*, seed: int, samples: int, path_class: str) -> Dict[str, Any]:
    rng = random.Random(seed + 7)
    log: List[bytes] = []
    queue_depth_max = 0
    latencies: List[float] = []
    group = 8 if path_class == "warm" else 1
    committed = 0
    pending: List[bytes] = []
    for i in range(samples):
        rec = struct.pack(">I", i) + bytes(rng.getrandbits(8) for _ in range(24))
        pending.append(rec)
        queue_depth_max = max(queue_depth_max, len(pending))
        if len(pending) >= group:
            t0 = time.perf_counter()
            log.extend(pending)
            committed += len(pending)
            pending.clear()
            latencies.append((time.perf_counter() - t0) * 1000.0)
    if pending:
        t0 = time.perf_counter()
        log.extend(pending)
        committed += len(pending)
        pending.clear()
        latencies.append((time.perf_counter() - t0) * 1000.0)
    wall = sum(latencies) / 1000.0 if latencies else 0.0
    stats = _latency_stats(latencies)
    return {
        "path_class": path_class,
        "committed_ops": committed,
        "committed_ops_per_s": (committed / wall) if wall > 0 else float(committed),
        "queue_depth_max": queue_depth_max,
        "ack_state": "committed",
        "log_records": len(log),
        **stats,
    }


def _measure_arc(*, seed: int, samples: int, path_class: str) -> Dict[str, Any]:
    rng = random.Random(seed + 11)
    capacity = 32
    cache: Dict[int, bytes] = {}
    hits = 0
    misses = 0
    evictions = 0
    miss_lat: List[float] = []
    keys = list(range(64 if path_class == "warm" else 48))
    # Optional warmup for warm path.
    if path_class == "warm":
        for k in keys[:capacity]:
            cache[k] = struct.pack(">I", k)
    for _ in range(samples):
        # Mild hot-set bias.
        if rng.random() < 0.7 and keys:
            key = keys[rng.randrange(0, min(8, len(keys)))]
        else:
            key = keys[rng.randrange(0, len(keys))]
        t0 = time.perf_counter()
        if key in cache:
            hits += 1
            _ = cache[key]
        else:
            misses += 1
            if len(cache) >= capacity:
                cache.pop(next(iter(cache)))
                evictions += 1
            cache[key] = struct.pack(">I", key)
            miss_lat.append((time.perf_counter() - t0) * 1000.0)
    total = hits + misses
    return {
        "path_class": path_class,
        "hits": hits,
        "misses": misses,
        "hit_ratio": (hits / total) if total else 0.0,
        "eviction_count": evictions,
        "miss_latency_ms": float(statistics.fmean(miss_lat)) if miss_lat else 0.0,
        "capacity": capacity,
    }


def run_baseline(profile_name: str = "ci-reference") -> Dict[str, Any]:
    workloads_doc = load_workloads()
    profiles = workloads_doc.get("resource_profiles") or {}
    if profile_name not in profiles:
        raise BaselineSchemaError(f"unknown profile {profile_name!r}")
    profile = profiles[profile_name]
    seed = int(profile.get("default_seed", 108108))
    warmup = int(profile.get("warmup_samples", 3))
    samples = int(profile.get("measurement_samples", 12))
    identity = build_identity(profile=profile, seed=seed)

    doctor = run_doctor()

    observations: Dict[str, Any] = {
        "sequential_io": {
            "cold": _measure_block_io(
                seed=seed,
                samples=samples,
                warmup=warmup,
                payload_bytes=4096,
                sequential=True,
                path_class="cold",
            ),
            "warm": _measure_block_io(
                seed=seed,
                samples=samples,
                warmup=warmup,
                payload_bytes=4096,
                sequential=True,
                path_class="warm",
            ),
        },
        "random_io": {
            "cold": _measure_block_io(
                seed=seed,
                samples=samples,
                warmup=warmup,
                payload_bytes=4096,
                sequential=False,
                path_class="cold",
            ),
            "warm": _measure_block_io(
                seed=seed,
                samples=samples,
                warmup=warmup,
                payload_bytes=4096,
                sequential=False,
                path_class="warm",
            ),
        },
        "metadata": {
            "cold": _measure_metadata(
                seed=seed, samples=samples, warmup=warmup, path_class="cold"
            ),
            "warm": _measure_metadata(
                seed=seed, samples=samples, warmup=warmup, path_class="warm"
            ),
        },
        "memory": _measure_memory(),
        "handles": {
            "cold": _measure_handles(seed=seed, samples=samples, path_class="cold"),
            "warm": _measure_handles(seed=seed, samples=samples, path_class="warm"),
        },
        "wal": {
            "cold": _measure_wal(seed=seed, samples=samples, path_class="cold"),
            "warm": _measure_wal(seed=seed, samples=samples, path_class="warm"),
        },
        "arc": {
            "cold": _measure_arc(seed=seed, samples=samples, path_class="cold"),
            "warm": _measure_arc(seed=seed, samples=samples, path_class="warm"),
        },
    }

    missing = [k for k in REQUIRED_BASELINE_OBSERVATIONS if k not in observations]
    if missing:
        raise BaselineSchemaError(f"missing baseline observations: {missing}")

    manifest = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "profile": profile_name,
        "identity": identity,
        "doctor": doctor,
        "path_classes": workloads_doc.get("path_classes"),
        "workloads": {
            name: workloads_doc["workloads"][name]
            for name in profile.get("workloads", [])
            if name in workloads_doc.get("workloads", {})
        },
        "observations": observations,
        "policy": {
            "native_mount": False,
            "driver_install": False,
            "production_import_mutation": False,
            "floors_status": "captured_not_reviewed",
            "note": (
                "KVFS-108 captures baselines; KVFS-801 freezes reviewed floors. "
                "Performance must not weaken correctness or durability."
            ),
        },
        "artifact_paths": {"workloads": WORKLOADS_PATH.name},
    }
    manifest["manifest_digest"] = _sha256_json(
        {
            "schema": SCHEMA,
            "task_id": TASK_ID,
            "profile": profile_name,
            "identity_digest": identity.get("identity_digest"),
            "observation_keys": sorted(observations),
            "doctor_digest": doctor.get("report_digest"),
        }
    )
    return manifest


def assert_workloads_valid(doc: Mapping[str, Any]) -> None:
    if doc.get("schema") != "KernelVFSWorkloadProfile@1":
        raise BaselineSchemaError("workloads schema must be KernelVFSWorkloadProfile@1")
    if doc.get("task_id") != TASK_ID:
        raise BaselineSchemaError(f"workloads task_id must be {TASK_ID}")
    profiles = doc.get("resource_profiles") or {}
    if "ci-reference" not in profiles:
        raise BaselineSchemaError("ci-reference profile is required")
    path_classes = doc.get("path_classes") or {}
    for required in ("cold", "warm"):
        if required not in path_classes:
            raise BaselineSchemaError(f"path_class {required!r} is required")
    workloads = doc.get("workloads") or {}
    profile = profiles["ci-reference"]
    for name in profile.get("workloads", []):
        if name not in workloads:
            raise BaselineSchemaError(f"profile references missing workload {name!r}")
    doctor_checks = doc.get("doctor_checks") or []
    for name in REQUIRED_DOCTOR_CHECKS:
        if name not in doctor_checks:
            raise BaselineSchemaError(f"doctor_checks missing {name!r}")
    identity_fields = doc.get("identity_fields") or []
    for field in ("seed", "dataset", "profile", "workload", "path_class"):
        if field not in identity_fields:
            raise BaselineSchemaError(f"identity_fields missing {field!r}")


def check_schema(profile_name: str = "ci-reference") -> Dict[str, Any]:
    """Validate static artifacts and produce a schema-bound micro baseline."""
    workloads_doc = load_workloads()
    assert_workloads_valid(workloads_doc)
    if profile_name not in workloads_doc["resource_profiles"]:
        raise BaselineSchemaError(f"unknown profile {profile_name!r}")

    profile = workloads_doc["resource_profiles"][profile_name]
    seed = int(profile.get("default_seed", 108108))
    identity = build_identity(profile=profile, seed=seed)
    for field in REQUIRED_IDENTITY_FIELDS:
        if field not in identity:
            raise BaselineSchemaError(f"identity missing {field!r}")

    doctor = run_doctor()
    for name in REQUIRED_DOCTOR_CHECKS:
        if name not in doctor["checks"]:
            raise BaselineSchemaError(f"doctor report missing check {name!r}")
    if not doctor["within_budget"]:
        raise BaselineSchemaError("doctor exceeded budget during schema check")
    if doctor.get("mounted"):
        raise BaselineSchemaError("doctor must never mount")

    # Micro observations prove measurement plumbing without full suite.
    micro = {
        "sequential_io": _measure_block_io(
            seed=seed,
            samples=4,
            warmup=1,
            payload_bytes=1024,
            sequential=True,
            path_class="warm",
        ),
        "metadata": _measure_metadata(seed=seed, samples=4, warmup=1, path_class="warm"),
        "memory": _measure_memory(),
        "handles": _measure_handles(seed=seed, samples=4, path_class="warm"),
        "wal": _measure_wal(seed=seed, samples=4, path_class="warm"),
        "arc": _measure_arc(seed=seed, samples=8, path_class="warm"),
        "random_io": _measure_block_io(
            seed=seed,
            samples=4,
            warmup=1,
            payload_bytes=1024,
            sequential=False,
            path_class="warm",
        ),
    }
    for key in REQUIRED_BASELINE_OBSERVATIONS:
        if key not in micro:
            raise BaselineSchemaError(f"micro baseline missing {key!r}")

    return {
        "ok": True,
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "profile": profile_name,
        "workloads_schema": workloads_doc.get("schema"),
        "identity_fields": list(REQUIRED_IDENTITY_FIELDS),
        "identity_digest": identity["identity_digest"],
        "seed": seed,
        "path_classes": sorted(workloads_doc["path_classes"]),
        "doctor_schema": doctor["schema"],
        "doctor_within_budget": doctor["within_budget"],
        "doctor_elapsed_seconds": doctor["elapsed_seconds"],
        "doctor_mounted": doctor["mounted"],
        "doctor_checks": sorted(doctor["checks"]),
        "observation_keys": sorted(micro),
        "native_mount": False,
        "policy": {
            "no_mount": True,
            "no_driver_install": True,
            "no_fusepy_import": True,
            "import_is_not_capability": True,
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="KVFS-108 kernel VFS bounded doctor and baseline harness"
    )
    p.add_argument(
        "--profile",
        default="ci-reference",
        help="Resource profile name from workloads.json (default: ci-reference)",
    )
    p.add_argument(
        "--check-schema",
        action="store_true",
        help="Validate workloads and doctor/baseline schema without full suite",
    )
    p.add_argument(
        "--run-doctor",
        action="store_true",
        help="Run only the bounded platform doctor",
    )
    p.add_argument(
        "--run",
        action="store_true",
        help="Execute doctor + hermetic baseline measurements",
    )
    p.add_argument(
        "--json-out",
        default=None,
        help="Optional path to write JSON output",
    )
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if not args.check_schema and not args.run and not args.run_doctor:
        args.check_schema = True

    try:
        if args.run:
            output: Dict[str, Any] = run_baseline(args.profile)
        elif args.run_doctor:
            output = run_doctor()
        else:
            output = check_schema(args.profile)
    except (BaselineSchemaError, DoctorBudgetError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1

    text = json.dumps(output, indent=2, sort_keys=True, default=str)
    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

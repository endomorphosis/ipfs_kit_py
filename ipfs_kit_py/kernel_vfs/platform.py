"""KVFS-503: Lazy fusepy/libfuse loading and bounded Linux capability doctor.

Importing this module is **inert**:

* it never imports ``fusepy`` / ``fuse``;
* it never ``dlopen``s libfuse;
* it never mounts, unmounts, or invokes fusermount.

Native binding and library load are explicit, architecture-aware entry points.
The Linux doctor probes fusepy presence, libfuse2 ABI, ``/dev/fuse``,
fusermount helper, permissions, and mountpoint/state separation within a hard
five-second budget. Missing capability is a typed, actionable error receipt —
never a silent success and never a mount attempt.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import platform
import shutil
import struct
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Identity / budgets
# ---------------------------------------------------------------------------

TASK_ID = "KVFS-503"
DOCTOR_SCHEMA = "KernelVFSLinuxDoctorReport@1"
SCHEMA_VERSION = "ipfs_kit_py.kernel_vfs.platform@1"
DOCTOR_BUDGET_SECONDS = 5.0
SUPPORTED_LIBFUSE_SONAME = "libfuse.so.2"
DEV_FUSE = "/dev/fuse"
FUSE_LIBRARY_PATH_ENV = "FUSE_LIBRARY_PATH"

# Doctor checks required by the Linux loader acceptance contract.
REQUIRED_DOCTOR_CHECKS: Tuple[str, ...] = (
    "os_architecture",
    "python_binding",
    "libfuse2_abi",
    "dev_fuse",
    "fusermount_helper",
    "permissions",
    "mountpoint_state_separation",
    "actionable_absence",
)

# Architecture → multiarch library directories (Debian/Ubuntu multiarch layout
# plus common /usr/lib64 and /lib layouts).
_ARCH_LIB_DIRS: Mapping[str, Tuple[str, ...]] = {
    "x86_64": (
        "/usr/lib/x86_64-linux-gnu",
        "/lib/x86_64-linux-gnu",
        "/usr/lib64",
        "/lib64",
        "/usr/lib",
        "/lib",
    ),
    "amd64": (
        "/usr/lib/x86_64-linux-gnu",
        "/lib/x86_64-linux-gnu",
        "/usr/lib64",
        "/lib64",
        "/usr/lib",
        "/lib",
    ),
    "aarch64": (
        "/usr/lib/aarch64-linux-gnu",
        "/lib/aarch64-linux-gnu",
        "/usr/lib64",
        "/lib64",
        "/usr/lib",
        "/lib",
    ),
    "arm64": (
        "/usr/lib/aarch64-linux-gnu",
        "/lib/aarch64-linux-gnu",
        "/usr/lib64",
        "/lib64",
        "/usr/lib",
        "/lib",
    ),
    "armv7l": (
        "/usr/lib/arm-linux-gnueabihf",
        "/lib/arm-linux-gnueabihf",
        "/usr/lib",
        "/lib",
    ),
    "ppc64le": (
        "/usr/lib/powerpc64le-linux-gnu",
        "/lib/powerpc64le-linux-gnu",
        "/usr/lib64",
        "/lib64",
        "/usr/lib",
        "/lib",
    ),
    "s390x": (
        "/usr/lib/s390x-linux-gnu",
        "/lib/s390x-linux-gnu",
        "/usr/lib64",
        "/lib64",
        "/usr/lib",
        "/lib",
    ),
    "riscv64": (
        "/usr/lib/riscv64-linux-gnu",
        "/lib/riscv64-linux-gnu",
        "/usr/lib",
        "/lib",
    ),
}

_FUSEMOUNT_CANDIDATES: Tuple[str, ...] = ("fusermount", "fusermount3")

# ---------------------------------------------------------------------------
# Module-private lazy state (never populated by import alone)
# ---------------------------------------------------------------------------

_binding_module: Optional[ModuleType] = None
_binding_name: Optional[str] = None
_libfuse_handle: Any = None
_libfuse_path: Optional[str] = None
_libfuse_loaded: bool = False


# ---------------------------------------------------------------------------
# Typed errors
# ---------------------------------------------------------------------------


class KernelVFSPlatformError(Exception):
    """Base error for kernel VFS platform / loader failures."""


class DoctorBudgetError(KernelVFSPlatformError):
    """Raised when the Linux capability doctor exceeds its hard time budget."""


class FuseCapabilityError(KernelVFSPlatformError):
    """Typed, actionable native FUSE capability failure.

    Attributes
    ----------
    check:
        Doctor check name that failed (or ``aggregate`` when several fail).
    message:
        Human-readable description of the absence/incompatibility.
    remediation:
        Actionable next step for the operator.
    support_claim:
        Always ``capability_unavailable`` for this error class.
    details:
        Optional structured diagnostic payload (never includes mount state).
    absences:
        List of ``{check, message}`` items when multiple checks failed.
    """

    support_claim = "capability_unavailable"

    def __init__(
        self,
        message: str,
        *,
        check: str,
        remediation: str,
        details: Optional[Mapping[str, Any]] = None,
        absences: Optional[Sequence[Mapping[str, Any]]] = None,
    ) -> None:
        self.check = check
        self.remediation = remediation
        self.details: Dict[str, Any] = dict(details or {})
        self.absences: List[Dict[str, Any]] = [dict(item) for item in (absences or ())]
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": type(self).__name__,
            "check": self.check,
            "message": str(self),
            "remediation": self.remediation,
            "support_claim": self.support_claim,
            "mounted": False,
            "details": dict(self.details),
            "absences": list(self.absences),
        }


# ---------------------------------------------------------------------------
# Public inert-state inspectors
# ---------------------------------------------------------------------------


def is_binding_loaded() -> bool:
    """Return True only after an explicit successful :func:`load_fuse_binding`."""
    return _binding_module is not None


def is_libfuse_loaded() -> bool:
    """Return True only after an explicit successful :func:`load_libfuse2`."""
    return _libfuse_loaded and _libfuse_handle is not None


def binding_module_name() -> Optional[str]:
    """Name of the loaded Python binding module, if any."""
    return _binding_name


def loaded_libfuse_path() -> Optional[str]:
    """Filesystem path of the dlopen'd libfuse2 library, if any."""
    return _libfuse_path


def reset_loader_state() -> None:
    """Clear cached binding/library handles (tests / process isolation).

    Does not unload a shared library from the process address space; it only
    forgets this module's references so the next explicit load re-resolves.
    """
    global _binding_module, _binding_name, _libfuse_handle, _libfuse_path, _libfuse_loaded
    _binding_module = None
    _binding_name = None
    _libfuse_handle = None
    _libfuse_path = None
    _libfuse_loaded = False


# ---------------------------------------------------------------------------
# Architecture-aware libfuse2 resolution (probe-only; no dlopen)
# ---------------------------------------------------------------------------


def normalize_machine(machine: Optional[str] = None) -> str:
    """Normalize :func:`platform.machine` to a canonical architecture token."""
    raw = (machine if machine is not None else platform.machine()) or ""
    token = raw.strip().lower()
    aliases = {
        "x64": "x86_64",
        "x86-64": "x86_64",
        "amd64": "x86_64",
        "arm64": "aarch64",
        "aarch64_be": "aarch64",
    }
    return aliases.get(token, token)


def architecture_lib_dirs(machine: Optional[str] = None) -> Tuple[str, ...]:
    """Return multiarch library search directories for *machine*."""
    arch = normalize_machine(machine)
    dirs = _ARCH_LIB_DIRS.get(arch)
    if dirs:
        return dirs
    # Unknown arch: still search generic locations without inventing multiarch.
    return ("/usr/lib64", "/lib64", "/usr/lib", "/lib")


def libfuse2_candidate_paths(
    *,
    machine: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
) -> List[str]:
    """Ordered candidate paths for the supported libfuse2 ABI.

    Resolution order:

    1. Explicit ``FUSE_LIBRARY_PATH`` when it names a ``libfuse.so.2`` path;
    2. Architecture-specific multiarch directories for ``libfuse.so.2``;
    3. Generic fallbacks.
    """
    environ = env if env is not None else os.environ
    ordered: List[str] = []
    seen: set[str] = set()

    def _add(path: str) -> None:
        if path and path not in seen:
            seen.add(path)
            ordered.append(path)

    explicit = (environ.get(FUSE_LIBRARY_PATH_ENV) or "").strip()
    if explicit:
        _add(explicit)

    for directory in architecture_lib_dirs(machine):
        _add(str(Path(directory) / SUPPORTED_LIBFUSE_SONAME))

    # Last-resort soname-only style paths used by some distributions.
    for fallback in (
        f"/usr/lib/{SUPPORTED_LIBFUSE_SONAME}",
        f"/lib/{SUPPORTED_LIBFUSE_SONAME}",
        f"/usr/lib64/{SUPPORTED_LIBFUSE_SONAME}",
        f"/lib64/{SUPPORTED_LIBFUSE_SONAME}",
    ):
        _add(fallback)

    return ordered


def resolve_libfuse2_path(
    *,
    machine: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
    require_exists: bool = True,
    allow_find_library: bool = True,
) -> Optional[str]:
    """Locate a libfuse2 shared library without loading it.

    When ``FUSE_LIBRARY_PATH`` is set it is preferred. If it does not exist or
    does not look like libfuse2, resolution continues over architecture-aware
    candidates (unless the explicit path exists and is used as-is for error
    reporting by the loader).

    When *allow_find_library* is False (doctor probes), only filesystem path
    candidates are consulted — ``ctypes.util.find_library`` may shell out to
    ``ldconfig``/``gcc`` and is reserved for explicit load resolution.
    """
    environ = env if env is not None else os.environ
    candidates = libfuse2_candidate_paths(machine=machine, env=environ)
    for path in candidates:
        if not require_exists:
            return path
        if os.path.isfile(path):
            # Prefer soname libfuse.so.2; accept explicit FUSE_LIBRARY_PATH even
            # if the basename differs (operator override).
            base = os.path.basename(path)
            if path == (environ.get(FUSE_LIBRARY_PATH_ENV) or "").strip():
                return path
            if base == SUPPORTED_LIBFUSE_SONAME or base.startswith("libfuse.so.2"):
                return path
    if not allow_find_library:
        return None
    # ctypes.util.find_library does not dlopen; use it as a last probe only.
    # Note: on Linux it may invoke ldconfig/gcc via subprocess — never call
    # from the bounded doctor path (set allow_find_library=False there).
    try:
        import ctypes.util

        resolved = ctypes.util.find_library("fuse")
    except Exception:
        resolved = None
    if resolved:
        # find_library may return a bare soname; only accept fuse2-shaped names.
        base = os.path.basename(resolved)
        if base == SUPPORTED_LIBFUSE_SONAME or base.startswith("libfuse.so.2"):
            if not require_exists or os.path.isfile(resolved) or "/" not in resolved:
                # Bare soname is acceptable for later dlopen via linker path.
                return resolved
    return None


def _path_looks_like_libfuse2(path: str) -> bool:
    base = os.path.basename(path)
    if base == SUPPORTED_LIBFUSE_SONAME or base.startswith("libfuse.so.2"):
        return True
    # Operator override via FUSE_LIBRARY_PATH may use a fully versioned path.
    return "libfuse.so.2" in base or base.endswith("libfuse.so.2.9.9")


# ---------------------------------------------------------------------------
# Explicit loaders (the only path that imports fusepy / dlopens libfuse)
# ---------------------------------------------------------------------------


def load_fuse_binding(*, force: bool = False) -> ModuleType:
    """Explicitly import the fusepy/fuse Python binding.

    This is intentionally **not** called at module import time. Importing the
    binding loads native code via ctypes; callers must opt in.
    """
    global _binding_module, _binding_name
    if _binding_module is not None and not force:
        return _binding_module

    errors: List[str] = []
    # fusepy historically installs the top-level module name ``fuse``.
    for name in ("fuse", "fusepy"):
        try:
            module = importlib.import_module(name)
        except ImportError as exc:
            errors.append(f"{name}: {exc}")
            continue
        _binding_module = module
        _binding_name = name
        return module

    raise FuseCapabilityError(
        "Python FUSE binding (fusepy) is not importable.",
        check="python_binding",
        remediation=(
            "Install the optional [fuse] extra (fusepy) for Linux host mounts: "
            "python -m pip install 'ipfs_kit_py[fuse]'. "
            "Package import success alone does not establish native FUSE capability."
        ),
        details={"import_errors": errors, "attempted_modules": ["fuse", "fusepy"]},
    )


def load_libfuse2(
    *,
    library_path: Optional[str] = None,
    machine: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
    force: bool = False,
) -> Any:
    """Explicitly ``dlopen`` the architecture-matched libfuse2 shared library.

    Parameters
    ----------
    library_path:
        Optional absolute path override (also accepts ``FUSE_LIBRARY_PATH``).
    machine:
        Architecture token override (defaults to :func:`platform.machine`).
    env:
        Environment mapping override (defaults to :data:`os.environ`).
    force:
        When True, re-resolve and reload even if a handle is cached.
    """
    global _libfuse_handle, _libfuse_path, _libfuse_loaded
    if _libfuse_loaded and _libfuse_handle is not None and not force:
        return _libfuse_handle

    environ = env if env is not None else os.environ
    path = (library_path or "").strip() or None
    if path is None:
        path = resolve_libfuse2_path(machine=machine, env=environ)

    if not path:
        arch = normalize_machine(machine)
        raise FuseCapabilityError(
            "libfuse2 (FUSE 2.x ABI) shared library was not found.",
            check="libfuse2_abi",
            remediation=(
                "Install libfuse2 compatibility libraries for the supported Linux "
                "fusepy high-level FUSE 2.x ABI profile "
                f"(architecture {arch!r}). "
                "You may also set FUSE_LIBRARY_PATH to an absolute libfuse.so.2 path."
            ),
            details={
                "architecture": arch,
                "candidates": libfuse2_candidate_paths(machine=machine, env=environ),
                "env_override": (environ.get(FUSE_LIBRARY_PATH_ENV) or None),
            },
        )

    # Import ctypes only at explicit load time so core import stays free of
    # accidental CDLL side effects from helper usage patterns.
    import ctypes

    try:
        handle = ctypes.CDLL(path)
    except OSError as exc:
        arch = normalize_machine(machine)
        raise FuseCapabilityError(
            f"Failed to load libfuse2 from {path!r}: {exc}",
            check="libfuse2_abi",
            remediation=(
                "Install a matching-architecture libfuse2 package or point "
                "FUSE_LIBRARY_PATH at a valid libfuse.so.2 for this Python process "
                f"(architecture {arch!r})."
            ),
            details={
                "architecture": arch,
                "library_path": path,
                "os_error": str(exc),
            },
        ) from exc

    _libfuse_handle = handle
    _libfuse_path = path
    _libfuse_loaded = True
    return handle


# ---------------------------------------------------------------------------
# Doctor probes (find_spec / path checks only — never import fusepy, never mount)
# ---------------------------------------------------------------------------


def _python_bits_label() -> str:
    """Return process pointer width (e.g. ``64bit``) without shelling out.

    ``platform.architecture()`` invokes the ``file`` utility via subprocess,
    which the doctor must never do (capability probes stay pure path/stat
    checks and must not execute external helpers).
    """
    return f"{struct.calcsize('P') * 8}bit"


def _probe_os_architecture() -> Dict[str, Any]:
    system = platform.system()
    machine = platform.machine()
    arch = normalize_machine(machine)
    supported = system == "Linux"
    # Prefer uname fields only — avoid platform.platform()/architecture() which
    # may subprocess to external utilities under some Python builds.
    try:
        uname = platform.uname()
        platform_label = (
            f"{uname.system}-{uname.release}-{uname.machine}"
            if uname.system
            else system
        )
    except Exception:  # pragma: no cover - defensive fallback
        platform_label = system
    return {
        "check": "os_architecture",
        "available": supported,
        "os": system,
        "architecture": machine,
        "architecture_normalized": arch,
        "python_bits": _python_bits_label(),
        "platform": platform_label,
        "python_version": platform.python_version(),
        "actionable_absence": None
        if supported
        else (
            f"OS {system!r} is outside the supported Linux fusepy/libfuse2 mount "
            "profile. Use a Linux host or the dedicated Linux FUSE container profile."
        ),
    }


def _probe_python_binding() -> Dict[str, Any]:
    """Record fusepy *presence* without importing (import loads native libs)."""
    fusepy_spec = importlib.util.find_spec("fusepy")
    fuse_spec = importlib.util.find_spec("fuse")
    present = fusepy_spec is not None or fuse_spec is not None
    already_imported = any(name in sys.modules for name in ("fusepy", "fuse"))
    return {
        "check": "python_binding",
        "available": present,
        "fusepy_find_spec": fusepy_spec is not None,
        "fuse_module_find_spec": fuse_spec is not None,
        "imported": False,  # this probe never imports
        "already_in_sys_modules": already_imported,
        "loader_binding_loaded": is_binding_loaded(),
        "note": "find_spec only; import is deferred because fusepy loads native code",
        "actionable_absence": None
        if present
        else (
            "Install the optional [fuse] extra (fusepy) for Linux host mounts. "
            "Package import success alone does not establish native FUSE capability."
        ),
    }


def _probe_libfuse2_abi(
    *,
    machine: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    environ = env if env is not None else os.environ
    arch = normalize_machine(machine)
    candidates = libfuse2_candidate_paths(machine=machine, env=environ)
    found: List[str] = []
    for path in candidates:
        if os.path.isfile(path):
            found.append(path)

    # Detect fuse3-only installs so the receipt is specific.
    fuse3_found: List[str] = []
    for directory in architecture_lib_dirs(machine):
        fuse3 = str(Path(directory) / "libfuse3.so.3")
        if os.path.isfile(fuse3):
            fuse3_found.append(fuse3)

    # Doctor path: path/stat only — never find_library (may subprocess).
    resolved = resolve_libfuse2_path(
        machine=machine, env=environ, allow_find_library=False
    )
    available = resolved is not None and os.path.isfile(resolved)

    if available:
        absence = None
    elif fuse3_found and not found:
        absence = (
            "Only libfuse3 was found; the supported Linux profile requires the "
            "libfuse2 (FUSE 2.x) ABI for fusepy's high-level binding. "
            "Install libfuse2 compatibility libraries "
            f"(architecture {arch!r})."
        )
    else:
        absence = (
            "Install libfuse2 compatibility libraries for the supported Linux "
            "fusepy high-level FUSE 2.x ABI profile "
            f"(architecture {arch!r}). "
            "Set FUSE_LIBRARY_PATH to an absolute libfuse.so.2 path if needed. "
            "This probe does not dlopen or mount."
        )

    return {
        "check": "libfuse2_abi",
        "available": bool(available),
        "architecture": arch,
        "soname": SUPPORTED_LIBFUSE_SONAME,
        "resolved_path": resolved,
        "candidates_checked": candidates,
        "found": found,
        "fuse3_found": fuse3_found,
        "loaded": is_libfuse_loaded(),
        "dlopen_performed": False,
        "actionable_absence": absence,
    }


def _probe_dev_fuse() -> Dict[str, Any]:
    exists = os.path.exists(DEV_FUSE)
    is_char = False
    accessible_rw = False
    mode: Optional[int] = None
    if exists:
        try:
            st = os.stat(DEV_FUSE)
            mode = int(st.st_mode)
            is_char = stat_is_char_device(st.st_mode)
        except OSError:
            is_char = False
        accessible_rw = os.access(DEV_FUSE, os.R_OK | os.W_OK)

    available = exists  # presence is the device check; permissions are separate
    return {
        "check": "dev_fuse",
        "available": available,
        "device": DEV_FUSE,
        "exists": exists,
        "is_char_device": is_char,
        "accessible_rw": accessible_rw,
        "mode": mode,
        "actionable_absence": None
        if available
        else (
            "Kernel FUSE device /dev/fuse is missing. Load the fuse module "
            "(e.g. modprobe fuse) or use a host/container profile that exposes "
            "it with --device /dev/fuse. This probe does not mount."
        ),
    }


def stat_is_char_device(mode: int) -> bool:
    """Return True if *mode* from :func:`os.stat` denotes a character device."""
    import stat as stat_mod

    return stat_mod.S_ISCHR(mode)


def _probe_fusermount_helper(
    *,
    path_env: Optional[str] = None,
) -> Dict[str, Any]:
    helpers: List[str] = []
    which_path = path_env if path_env is not None else os.environ.get("PATH", "")
    # Use shutil.which with explicit path so validation PATH is honored.
    for name in _FUSEMOUNT_CANDIDATES:
        located = shutil.which(name, path=which_path)
        if located:
            helpers.append(located)

    # Prefer classic fusermount (fuse2) when both exist.
    fuse2_helpers = [h for h in helpers if os.path.basename(h) == "fusermount"]
    preferred = fuse2_helpers[0] if fuse2_helpers else (helpers[0] if helpers else None)

    return {
        "check": "fusermount_helper",
        "available": bool(helpers),
        "helpers": helpers,
        "preferred": preferred,
        "invoked": False,
        "actionable_absence": None
        if helpers
        else (
            "Neither fusermount nor fusermount3 is on PATH. Install fuse/fuse2 "
            "userspace helpers (package often named fuse or fuse2). "
            "This probe does not invoke mount helpers."
        ),
    }


def _probe_permissions(
    *,
    mountpoint: Optional[Path] = None,
    state_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Probe /dev/fuse and directory permissions without mounting."""
    dev = _probe_dev_fuse()
    dev_ok = bool(dev.get("exists")) and bool(dev.get("accessible_rw"))

    mount_ok: Optional[bool] = None
    state_ok: Optional[bool] = None
    mount_path = str(mountpoint) if mountpoint is not None else None
    state_path = str(state_dir) if state_dir is not None else None

    if mountpoint is not None:
        mount_ok = mountpoint.is_dir() and os.access(
            mountpoint, os.R_OK | os.W_OK | os.X_OK
        )
    if state_dir is not None:
        state_ok = state_dir.is_dir() and os.access(
            state_dir, os.R_OK | os.W_OK | os.X_OK
        )

    # Permissions check is available when we can evaluate the device and any
    # provided directories. When dirs are omitted, device RW is the gate.
    if mountpoint is None and state_dir is None:
        available = dev_ok
        absence = None
        if not dev.get("exists"):
            absence = (
                "Cannot evaluate FUSE permissions because /dev/fuse is missing. "
                "Expose /dev/fuse and ensure the mounting user can read/write it."
            )
        elif not dev_ok:
            absence = (
                "The mounting user cannot read/write /dev/fuse. Add the user to "
                "the fuse group (or adjust device node permissions) and re-login. "
                "This probe does not mount."
            )
    else:
        dir_ok = True
        if mount_ok is not None:
            dir_ok = dir_ok and mount_ok
        if state_ok is not None:
            dir_ok = dir_ok and state_ok
        available = dev_ok and dir_ok
        if not available:
            parts: List[str] = []
            if not dev_ok:
                parts.append(
                    "/dev/fuse is missing or not read/write for this user"
                )
            if mount_ok is False:
                parts.append(f"mountpoint {mount_path!r} is not accessible")
            if state_ok is False:
                parts.append(f"state directory {state_path!r} is not accessible")
            absence = (
                "; ".join(parts)
                + ". Fix permissions before mounting; this probe does not mount."
            )
        else:
            absence = None

    return {
        "check": "permissions",
        "available": available,
        "dev_fuse_exists": bool(dev.get("exists")),
        "dev_fuse_accessible_rw": bool(dev.get("accessible_rw")),
        "mountpoint": mount_path,
        "state_dir": state_path,
        "mountpoint_accessible": mount_ok,
        "state_accessible": state_ok,
        "actionable_absence": absence,
    }


def _probe_mountpoint_state_separation(
    *,
    mountpoint: Optional[os.PathLike[str] | str] = None,
    state_dir: Optional[os.PathLike[str] | str] = None,
) -> Dict[str, Any]:
    """Verify mountpoint and state directories are distinct and usable.

    When paths are omitted, creates disposable directories under a temporary
    base and removes them afterward — never mounts.
    """
    created_base: Optional[Path] = None
    try:
        if mountpoint is None or state_dir is None:
            created_base = Path(tempfile.mkdtemp(prefix="kvfs503-doctor-"))
            mp = Path(mountpoint) if mountpoint is not None else created_base / "mnt"
            st = Path(state_dir) if state_dir is not None else created_base / "state"
            if mountpoint is None:
                mp.mkdir(mode=0o755, exist_ok=True)
            if state_dir is None:
                st.mkdir(mode=0o700, exist_ok=True)
        else:
            mp = Path(mountpoint)
            st = Path(state_dir)

        mount_ok = mp.is_dir() and os.access(mp, os.R_OK | os.W_OK | os.X_OK)
        state_ok = st.is_dir() and os.access(st, os.R_OK | os.W_OK | os.X_OK)

        try:
            same_path = mp.resolve() == st.resolve()
        except OSError:
            same_path = os.path.normpath(str(mp)) == os.path.normpath(str(st))

        # Nested state under mountpoint is also forbidden (lost on unmount).
        nested = False
        try:
            mp_res = mp.resolve()
            st_res = st.resolve()
            if not same_path:
                try:
                    st_res.relative_to(mp_res)
                    nested = True
                except ValueError:
                    nested = False
        except OSError:
            nested = False

        separated = (not same_path) and (not nested)
        available = mount_ok and state_ok and separated

        if available:
            absence = None
        elif same_path:
            absence = (
                "Mountpoint and state directory resolve to the same path. "
                "Keep recovery/WAL/cache state outside the mountpoint."
            )
        elif nested:
            absence = (
                "State directory is nested under the mountpoint. "
                "WAL/cache/state must live on a separate host path that survives unmount."
            )
        else:
            absence = (
                "Mountpoint and state directories must be writable and distinct. "
                "Never co-locate recovery state on the mountpoint."
            )

        return {
            "check": "mountpoint_state_separation",
            "available": available,
            "mountpoint": str(mp),
            "state_dir": str(st),
            "mountpoint_accessible": mount_ok,
            "state_accessible": state_ok,
            "same_path": same_path,
            "state_nested_under_mountpoint": nested,
            "separated": separated,
            "mounted": False,
            "actionable_absence": absence,
        }
    finally:
        if created_base is not None:
            shutil.rmtree(created_base, ignore_errors=True)


def _collect_absences(checks: Mapping[str, Mapping[str, Any]]) -> List[Dict[str, str]]:
    absences: List[Dict[str, str]] = []
    for name in REQUIRED_DOCTOR_CHECKS:
        if name == "actionable_absence":
            continue
        entry = checks.get(name) or {}
        msg = entry.get("actionable_absence")
        if msg:
            absences.append({"check": name, "message": str(msg)})
    return absences


def run_linux_doctor(
    *,
    budget_seconds: float = DOCTOR_BUDGET_SECONDS,
    mountpoint: Optional[os.PathLike[str] | str] = None,
    state_dir: Optional[os.PathLike[str] | str] = None,
    env: Optional[Mapping[str, str]] = None,
    path_env: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the bounded Linux FUSE capability doctor.

    Never mounts, never imports fusepy, never dlopens libfuse. Completes within
    *budget_seconds* or raises :class:`DoctorBudgetError`.
    """
    started = time.perf_counter()
    environ = env if env is not None else os.environ
    machine = platform.machine()

    mp_path = Path(mountpoint) if mountpoint is not None else None
    st_path = Path(state_dir) if state_dir is not None else None

    checks: Dict[str, Any] = {}
    checks["os_architecture"] = _probe_os_architecture()
    checks["python_binding"] = _probe_python_binding()
    checks["libfuse2_abi"] = _probe_libfuse2_abi(machine=machine, env=environ)
    checks["dev_fuse"] = _probe_dev_fuse()
    checks["fusermount_helper"] = _probe_fusermount_helper(path_env=path_env)
    checks["permissions"] = _probe_permissions(
        mountpoint=mp_path, state_dir=st_path
    )
    checks["mountpoint_state_separation"] = _probe_mountpoint_state_separation(
        mountpoint=mountpoint, state_dir=state_dir
    )

    absences = _collect_absences(checks)
    checks["actionable_absence"] = {
        "check": "actionable_absence",
        "available": True,
        "count": len(absences),
        "items": absences,
        "policy": (
            "Missing native capability is a typed terminal receipt for this run; "
            "it never leaves a probe running, never mounts, and never claims "
            "support from package import alone."
        ),
    }

    elapsed = time.perf_counter() - started
    if elapsed > budget_seconds:
        raise DoctorBudgetError(
            f"Linux FUSE doctor exceeded budget: {elapsed:.3f}s > {budget_seconds:.3f}s"
        )

    # Native readiness requires the Linux profile primitives. Permissions and
    # mountpoint/state separation must also pass when they are evaluable.
    readiness_keys = (
        "os_architecture",
        "python_binding",
        "libfuse2_abi",
        "dev_fuse",
        "fusermount_helper",
        "permissions",
        "mountpoint_state_separation",
    )
    native_ready = all(bool(checks[k].get("available")) for k in readiness_keys)

    report: Dict[str, Any] = {
        "schema": DOCTOR_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "elapsed_seconds": elapsed,
        "budget_seconds": budget_seconds,
        "within_budget": elapsed <= budget_seconds,
        "mounted": False,
        "native_capability_ready": native_ready,
        "support_claim": (
            "probe_passed" if native_ready else "capability_unavailable"
        ),
        "checks": checks,
        "required_checks": list(REQUIRED_DOCTOR_CHECKS),
        "policy": {
            "no_mount": True,
            "no_driver_install": True,
            "no_fusepy_import": True,
            "no_libfuse_dlopen": True,
            "import_is_not_capability": True,
            "budget_seconds": budget_seconds,
            "supported_abi": "libfuse2",
            "supported_binding": "fusepy_high_level_fuse2",
        },
        "loader": {
            "binding_loaded": is_binding_loaded(),
            "libfuse_loaded": is_libfuse_loaded(),
            "binding_name": binding_module_name(),
            "libfuse_path": loaded_libfuse_path(),
        },
    }
    return report


# Alias used by lifecycle / packaging callers.
run_doctor = run_linux_doctor


def ensure_linux_fuse_capability(
    *,
    budget_seconds: float = DOCTOR_BUDGET_SECONDS,
    mountpoint: Optional[os.PathLike[str] | str] = None,
    state_dir: Optional[os.PathLike[str] | str] = None,
    env: Optional[Mapping[str, str]] = None,
    path_env: Optional[str] = None,
    load_binding: bool = False,
    load_native: bool = False,
) -> Dict[str, Any]:
    """Run the doctor and raise :class:`FuseCapabilityError` when not ready.

    Never mounts. Optional *load_binding* / *load_native* perform explicit
    loads only after the probe-only doctor passes.
    """
    report = run_linux_doctor(
        budget_seconds=budget_seconds,
        mountpoint=mountpoint,
        state_dir=state_dir,
        env=env,
        path_env=path_env,
    )
    if not report["native_capability_ready"]:
        items = report["checks"]["actionable_absence"]["items"]
        if items:
            primary = items[0]
            check = str(primary["check"])
            message = str(primary["message"])
        else:
            check = "aggregate"
            message = (
                "Linux FUSE capability is unavailable; see doctor report for details."
            )
        remediation = message
        raise FuseCapabilityError(
            message,
            check=check,
            remediation=remediation,
            details={
                "support_claim": report["support_claim"],
                "elapsed_seconds": report["elapsed_seconds"],
                "mounted": False,
            },
            absences=items,
        )

    if load_binding:
        load_fuse_binding()
    if load_native:
        load_libfuse2(env=env)

    report["loader"] = {
        "binding_loaded": is_binding_loaded(),
        "libfuse_loaded": is_libfuse_loaded(),
        "binding_name": binding_module_name(),
        "libfuse_path": loaded_libfuse_path(),
    }
    return report


@dataclass
class LinuxFusePlatform:
    """Small façade for lifecycle code that needs explicit load + doctor.

    Instantiation is inert; methods perform probes/loads on demand.
    """

    budget_seconds: float = DOCTOR_BUDGET_SECONDS
    _last_report: Optional[Dict[str, Any]] = field(default=None, repr=False)

    def doctor(
        self,
        *,
        mountpoint: Optional[os.PathLike[str] | str] = None,
        state_dir: Optional[os.PathLike[str] | str] = None,
    ) -> Dict[str, Any]:
        self._last_report = run_linux_doctor(
            budget_seconds=self.budget_seconds,
            mountpoint=mountpoint,
            state_dir=state_dir,
        )
        return self._last_report

    def ensure(
        self,
        *,
        mountpoint: Optional[os.PathLike[str] | str] = None,
        state_dir: Optional[os.PathLike[str] | str] = None,
        load_binding: bool = False,
        load_native: bool = False,
    ) -> Dict[str, Any]:
        self._last_report = ensure_linux_fuse_capability(
            budget_seconds=self.budget_seconds,
            mountpoint=mountpoint,
            state_dir=state_dir,
            load_binding=load_binding,
            load_native=load_native,
        )
        return self._last_report

    def load_binding(self, *, force: bool = False) -> ModuleType:
        return load_fuse_binding(force=force)

    def load_libfuse2(self, *, library_path: Optional[str] = None, force: bool = False) -> Any:
        return load_libfuse2(library_path=library_path, force=force)

    @property
    def last_report(self) -> Optional[Dict[str, Any]]:
        return self._last_report


__all__ = [
    "TASK_ID",
    "DOCTOR_SCHEMA",
    "SCHEMA_VERSION",
    "DOCTOR_BUDGET_SECONDS",
    "SUPPORTED_LIBFUSE_SONAME",
    "DEV_FUSE",
    "FUSE_LIBRARY_PATH_ENV",
    "REQUIRED_DOCTOR_CHECKS",
    "KernelVFSPlatformError",
    "DoctorBudgetError",
    "FuseCapabilityError",
    "is_binding_loaded",
    "is_libfuse_loaded",
    "binding_module_name",
    "loaded_libfuse_path",
    "reset_loader_state",
    "normalize_machine",
    "architecture_lib_dirs",
    "libfuse2_candidate_paths",
    "resolve_libfuse2_path",
    "load_fuse_binding",
    "load_libfuse2",
    "run_linux_doctor",
    "run_doctor",
    "ensure_linux_fuse_capability",
    "LinuxFusePlatform",
]

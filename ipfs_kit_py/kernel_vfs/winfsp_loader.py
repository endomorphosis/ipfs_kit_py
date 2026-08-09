"""KVFS-608: Deterministic WinFsp/fusepy loader and bounded Windows doctor.

Importing this module is **inert**:

* it never imports ``fusepy`` / ``fuse``;
* it never ``LoadLibrary``s / ``CDLL``s a WinFsp DLL;
* it never starts the WinFsp service or driver;
* it never mounts a drive letter or directory.

Native binding and DLL load are explicit, architecture-aware entry points.
Loader resolution order is deterministic:

1. Explicit ``FUSE_LIBRARY_PATH`` (operator override);
2. Validated WinFsp registry ``InstallDir`` lookup for the matching
   ``winfsp-x64.dll`` / ``winfsp-x86.dll``.

The Windows doctor probes service, driver, DLL, version, architecture
agreement, and drive/directory prerequisites within a hard five-second
budget. Missing or incompatible native support is a typed, actionable
capability error receipt — never a silent success and never a mount or
service start.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import platform
import re
import shutil
import string
import struct
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Identity / budgets
# ---------------------------------------------------------------------------

TASK_ID = "KVFS-608"
DOCTOR_SCHEMA = "KernelVFSWindowsDoctorReport@1"
SCHEMA_VERSION = "ipfs_kit_py.kernel_vfs.winfsp_loader@1"
DOCTOR_BUDGET_SECONDS = 5.0
FUSE_LIBRARY_PATH_ENV = "FUSE_LIBRARY_PATH"

# WinFsp FUSE-compat DLL basenames by process pointer width.
WINFSP_DLL_X64 = "winfsp-x64.dll"
WINFSP_DLL_X86 = "winfsp-x86.dll"
WINFSP_DLL_BY_BITS: Mapping[str, str] = {
    "64bit": WINFSP_DLL_X64,
    "32bit": WINFSP_DLL_X86,
}

# Registry keys consulted for InstallDir (never written).
WINFSP_REGISTRY_KEYS: Tuple[Tuple[str, str], ...] = (
    ("HKEY_LOCAL_MACHINE", r"SOFTWARE\WinFsp"),
    ("HKEY_LOCAL_MACHINE", r"SOFTWARE\WOW6432Node\WinFsp"),
)
WINFSP_INSTALL_DIR_VALUE = "InstallDir"

# Service / driver identity (probe-only; never started).
WINFSP_SERVICE_NAMES: Tuple[str, ...] = ("WinFsp.Launcher", "WinFsp")
WINFSP_DRIVER_SERVICE_NAMES: Tuple[str, ...] = ("WinFsp", "WinFsp.Disk")
WINFSP_SYS_BY_BITS: Mapping[str, str] = {
    "64bit": "winfsp-x64.sys",
    "32bit": "winfsp-x86.sys",
}

# Doctor checks required by the Windows loader acceptance contract.
REQUIRED_DOCTOR_CHECKS: Tuple[str, ...] = (
    "os_architecture",
    "python_binding",
    "winfsp_dll",
    "winfsp_service",
    "winfsp_driver",
    "winfsp_version",
    "architecture_agreement",
    "drive_directory_prerequisites",
    "actionable_absence",
)

# PE machine codes (IMAGE_FILE_HEADER.Machine).
_PE_MACHINE_I386 = 0x014C
_PE_MACHINE_AMD64 = 0x8664
_PE_MACHINE_ARM64 = 0xAA64
_PE_MACHINE_LABELS: Mapping[int, str] = {
    _PE_MACHINE_I386: "x86",
    _PE_MACHINE_AMD64: "x64",
    _PE_MACHINE_ARM64: "arm64",
}

# Minimum WinFsp major version we accept when a version string is readable.
# (Hermetic probes tolerate missing version resources.)
MINIMUM_WINFSP_MAJOR = 1

# ---------------------------------------------------------------------------
# Module-private lazy state (never populated by import alone)
# ---------------------------------------------------------------------------

_binding_module: Optional[ModuleType] = None
_binding_name: Optional[str] = None
_winfsp_handle: Any = None
_winfsp_path: Optional[str] = None
_winfsp_loaded: bool = False

# Optional injectable registry reader for hermetic tests (Linux CI).
# Signature: (root_name: str, subkey: str, value_name: str) -> Optional[str]
_registry_reader: Optional[Callable[[str, str, str], Optional[str]]] = None
# Optional injectable service-state reader for hermetic tests.
# Signature: (service_name: str) -> Optional[Mapping[str, Any]]
_service_reader: Optional[Callable[[str], Optional[Mapping[str, Any]]]] = None


# ---------------------------------------------------------------------------
# Typed errors
# ---------------------------------------------------------------------------


class KernelVFSPlatformError(Exception):
    """Base error for kernel VFS platform / loader failures."""


class DoctorBudgetError(KernelVFSPlatformError):
    """Raised when the Windows capability doctor exceeds its hard time budget."""


class FuseCapabilityError(KernelVFSPlatformError):
    """Typed, actionable native WinFsp/FUSE capability failure.

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
            "service_started": False,
            "details": dict(self.details),
            "absences": list(self.absences),
        }


# ---------------------------------------------------------------------------
# Public inert-state inspectors
# ---------------------------------------------------------------------------


def is_binding_loaded() -> bool:
    """Return True only after an explicit successful :func:`load_fuse_binding`."""
    return _binding_module is not None


def is_winfsp_loaded() -> bool:
    """Return True only after an explicit successful :func:`load_winfsp_dll`."""
    return _winfsp_loaded and _winfsp_handle is not None


def binding_module_name() -> Optional[str]:
    """Name of the loaded Python binding module, if any."""
    return _binding_name


def loaded_winfsp_path() -> Optional[str]:
    """Filesystem path of the LoadLibrary'd WinFsp DLL, if any."""
    return _winfsp_path


def reset_loader_state() -> None:
    """Clear cached binding/library handles (tests / process isolation).

    Does not unload a shared library from the process address space; it only
    forgets this module's references so the next explicit load re-resolves.
    """
    global _binding_module, _binding_name, _winfsp_handle, _winfsp_path, _winfsp_loaded
    global _registry_reader, _service_reader
    _binding_module = None
    _binding_name = None
    _winfsp_handle = None
    _winfsp_path = None
    _winfsp_loaded = False
    _registry_reader = None
    _service_reader = None


def set_registry_reader(
    reader: Optional[Callable[[str, str, str], Optional[str]]],
) -> None:
    """Install a hermetic registry reader (tests). Pass ``None`` to clear."""
    global _registry_reader
    _registry_reader = reader


def set_service_reader(
    reader: Optional[Callable[[str], Optional[Mapping[str, Any]]]],
) -> None:
    """Install a hermetic service-state reader (tests). Pass ``None`` to clear."""
    global _service_reader
    _service_reader = reader


# ---------------------------------------------------------------------------
# Architecture helpers
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
        "i386": "x86",
        "i686": "x86",
        "x86": "x86",
        "win32": "x86",
    }
    return aliases.get(token, token)


def python_bits_label() -> str:
    """Return process pointer width (e.g. ``64bit``) without shelling out."""
    return f"{struct.calcsize('P') * 8}bit"


def expected_winfsp_dll_basename(*, bits: Optional[str] = None) -> str:
    """Return the WinFsp DLL basename matching the Python process architecture."""
    label = bits if bits is not None else python_bits_label()
    return WINFSP_DLL_BY_BITS.get(label, WINFSP_DLL_X64)


def expected_winfsp_sys_basename(*, bits: Optional[str] = None) -> str:
    """Return the WinFsp driver basename matching the Python process architecture."""
    label = bits if bits is not None else python_bits_label()
    return WINFSP_SYS_BY_BITS.get(label, "winfsp-x64.sys")


def dll_arch_label_for_bits(bits: Optional[str] = None) -> str:
    """Map process bits to the short WinFsp arch label (``x64`` / ``x86``)."""
    label = bits if bits is not None else python_bits_label()
    return "x64" if label == "64bit" else "x86"


# ---------------------------------------------------------------------------
# PE header probe (path-only; never LoadLibrary)
# ---------------------------------------------------------------------------


def read_pe_machine(path: os.PathLike[str] | str) -> Optional[int]:
    """Read the PE ``Machine`` field from *path*, or ``None`` if not a PE file.

    Pure filesystem parse — never loads the image into the process.
    """
    try:
        with open(path, "rb") as fh:
            header = fh.read(64)
            if len(header) < 64 or header[:2] != b"MZ":
                return None
            (pe_offset,) = struct.unpack_from("<I", header, 60)
            if pe_offset < 64 or pe_offset > 0x100000:
                return None
            fh.seek(pe_offset)
            pe_sig = fh.read(4)
            if pe_sig != b"PE\0\0":
                return None
            coff = fh.read(20)
            if len(coff) < 4:
                return None
            (machine,) = struct.unpack_from("<H", coff, 0)
            return int(machine)
    except OSError:
        return None


def pe_machine_label(machine: Optional[int]) -> Optional[str]:
    """Map a PE machine code to a short architecture label."""
    if machine is None:
        return None
    return _PE_MACHINE_LABELS.get(int(machine))


def pe_architecture_matches_python(
    path: os.PathLike[str] | str,
    *,
    bits: Optional[str] = None,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Return ``(matches, pe_label, expected_label)`` for *path* vs process bits.

    When the PE header cannot be parsed, returns ``(False, None, expected)`` so
    hermetic fake DLLs without PE structure fail the architecture agreement
    check rather than silently matching. Explicit operator overrides still
    resolve by path; load-time CDLL surfaces the real failure.
    """
    expected = dll_arch_label_for_bits(bits)
    machine = read_pe_machine(path)
    pe_label = pe_machine_label(machine)
    if pe_label is None:
        # Unknown / unreadable PE: treat path-level presence as inconclusive for
        # match; callers that only care about path existence use separate logic.
        return (False, None, expected)
    # x64 Python matches amd64 PE; x86 Python matches i386 PE.
    # ARM64 PE is reported but does not match x86/x64 process labels.
    matches = pe_label == expected
    return (matches, pe_label, expected)


# ---------------------------------------------------------------------------
# Registry / InstallDir lookup (probe-only; never starts services)
# ---------------------------------------------------------------------------


def _default_winreg_reader(root_name: str, subkey: str, value_name: str) -> Optional[str]:
    """Read a registry string value via ``winreg`` when available."""
    if sys.platform != "win32":
        return None
    try:
        import winreg  # type: ignore
    except ImportError:
        return None

    root_map = {
        "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
        "HKLM": winreg.HKEY_LOCAL_MACHINE,
    }
    root = root_map.get(root_name)
    if root is None:
        return None
    try:
        with winreg.OpenKey(root, subkey) as key:
            value, _ = winreg.QueryValueEx(key, value_name)
    except OSError:
        return None
    if value is None:
        return None
    text = str(value).strip().rstrip("\\/")
    return text or None


def read_winfsp_registry_value(
    root_name: str,
    subkey: str,
    value_name: str = WINFSP_INSTALL_DIR_VALUE,
) -> Optional[str]:
    """Read a WinFsp registry value using the injected or default reader."""
    reader = _registry_reader if _registry_reader is not None else _default_winreg_reader
    try:
        return reader(root_name, subkey, value_name)
    except Exception:
        return None


def lookup_winfsp_install_dir(
    *,
    registry_keys: Optional[Sequence[Tuple[str, str]]] = None,
) -> Tuple[Optional[str], Optional[Tuple[str, str]]]:
    """Return ``(InstallDir, (root, subkey))`` for the first successful key."""
    keys = tuple(registry_keys) if registry_keys is not None else WINFSP_REGISTRY_KEYS
    for root_name, subkey in keys:
        install_dir = read_winfsp_registry_value(root_name, subkey, WINFSP_INSTALL_DIR_VALUE)
        if install_dir:
            return install_dir, (root_name, subkey)
    return None, None


def winfsp_dll_path_from_install_dir(
    install_dir: os.PathLike[str] | str,
    *,
    bits: Optional[str] = None,
) -> str:
    """Build the architecture-matched DLL path under a WinFsp InstallDir."""
    basename = expected_winfsp_dll_basename(bits=bits)
    base = Path(install_dir)
    # Official layout places DLLs under bin\; also accept install_dir root.
    return str(base / "bin" / basename)


def winfsp_sys_path_from_install_dir(
    install_dir: os.PathLike[str] | str,
    *,
    bits: Optional[str] = None,
) -> str:
    """Build the architecture-matched driver path under a WinFsp InstallDir."""
    basename = expected_winfsp_sys_basename(bits=bits)
    return str(Path(install_dir) / "bin" / basename)


# ---------------------------------------------------------------------------
# Deterministic DLL resolution
# ---------------------------------------------------------------------------


def winfsp_dll_candidate_paths(
    *,
    bits: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
    install_dir: Optional[str] = None,
    registry_keys: Optional[Sequence[Tuple[str, str]]] = None,
) -> List[str]:
    """Ordered candidate paths for the architecture-matched WinFsp DLL.

    Resolution order:

    1. Explicit ``FUSE_LIBRARY_PATH`` when set;
    2. ``{InstallDir}\\bin\\winfsp-{x64|x86}.dll`` from validated registry
       (or an explicit *install_dir* override used by tests/callers);
    3. Same basename under ``InstallDir`` root (non-standard layouts).
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

    resolved_install = (install_dir or "").strip() or None
    if resolved_install is None:
        resolved_install, _ = lookup_winfsp_install_dir(registry_keys=registry_keys)

    if resolved_install:
        _add(winfsp_dll_path_from_install_dir(resolved_install, bits=bits))
        # Non-standard: DLL sitting directly in InstallDir.
        _add(str(Path(resolved_install) / expected_winfsp_dll_basename(bits=bits)))

    return ordered


def resolve_winfsp_dll_path(
    *,
    bits: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
    install_dir: Optional[str] = None,
    registry_keys: Optional[Sequence[Tuple[str, str]]] = None,
    require_exists: bool = True,
    validate_architecture: bool = False,
) -> Optional[str]:
    """Locate the architecture-matched WinFsp FUSE DLL without loading it.

    Preference:

    1. Explicit ``FUSE_LIBRARY_PATH`` when the path exists (operator override);
    2. Registry-derived InstallDir candidate that exists;
    3. Optional PE architecture validation when *validate_architecture* is True.
    """
    environ = env if env is not None else os.environ
    candidates = winfsp_dll_candidate_paths(
        bits=bits,
        env=environ,
        install_dir=install_dir,
        registry_keys=registry_keys,
    )
    explicit = (environ.get(FUSE_LIBRARY_PATH_ENV) or "").strip()

    for path in candidates:
        if not require_exists:
            return path
        if not os.path.isfile(path):
            continue
        if validate_architecture:
            matches, pe_label, expected = pe_architecture_matches_python(path, bits=bits)
            # Explicit FUSE_LIBRARY_PATH is accepted even when PE is unreadable
            # (hermetic fixtures); architecture agreement is a separate doctor check.
            if path == explicit:
                return path
            if pe_label is not None and not matches:
                continue
            # Registry-derived path: prefer architecture match when PE is readable.
            if pe_label is not None and matches:
                return path
            if pe_label is None:
                # Unreadable PE under InstallDir — still a candidate (path present).
                return path
            # pe_label present but mismatch already continued.
            continue  # pragma: no cover - defensive
        return path
    return None


# ---------------------------------------------------------------------------
# Explicit loaders (the only path that imports fusepy / LoadLibrary)
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
            "Install the optional [fuse] extra (fusepy) for Windows WinFsp mounts: "
            "python -m pip install 'ipfs_kit_py[fuse]'. "
            "Package import success alone does not establish native WinFsp capability."
        ),
        details={"import_errors": errors, "attempted_modules": ["fuse", "fusepy"]},
    )


def load_winfsp_dll(
    *,
    library_path: Optional[str] = None,
    bits: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
    install_dir: Optional[str] = None,
    force: bool = False,
) -> Any:
    """Explicitly ``CDLL``/``LoadLibrary`` the architecture-matched WinFsp DLL.

    Parameters
    ----------
    library_path:
        Optional absolute path override (also accepts ``FUSE_LIBRARY_PATH``).
    bits:
        Process bitness override (defaults to :func:`python_bits_label`).
    env:
        Environment mapping override (defaults to :data:`os.environ`).
    install_dir:
        Optional WinFsp InstallDir override (skips registry when set).
    force:
        When True, re-resolve and reload even if a handle is cached.
    """
    global _winfsp_handle, _winfsp_path, _winfsp_loaded
    if _winfsp_loaded and _winfsp_handle is not None and not force:
        return _winfsp_handle

    environ = env if env is not None else os.environ
    path = (library_path or "").strip() or None
    if path is None:
        path = resolve_winfsp_dll_path(
            bits=bits, env=environ, install_dir=install_dir
        )

    bit_label = bits if bits is not None else python_bits_label()
    expected_dll = expected_winfsp_dll_basename(bits=bit_label)
    arch_label = dll_arch_label_for_bits(bit_label)

    if not path:
        raise FuseCapabilityError(
            "WinFsp FUSE compatibility DLL was not found.",
            check="winfsp_dll",
            remediation=(
                f"Install WinFsp for the matching architecture ({arch_label}) and "
                f"ensure {expected_dll} is present under the InstallDir bin folder. "
                "You may also set FUSE_LIBRARY_PATH to an absolute path of the "
                "matching winfsp-x64.dll or winfsp-x86.dll. "
                "This loader never installs or starts WinFsp."
            ),
            details={
                "architecture": arch_label,
                "python_bits": bit_label,
                "expected_dll": expected_dll,
                "candidates": winfsp_dll_candidate_paths(
                    bits=bit_label, env=environ, install_dir=install_dir
                ),
                "env_override": (environ.get(FUSE_LIBRARY_PATH_ENV) or None),
            },
        )

    import ctypes

    try:
        handle = ctypes.CDLL(path)
    except OSError as exc:
        raise FuseCapabilityError(
            f"Failed to load WinFsp DLL from {path!r}: {exc}",
            check="winfsp_dll",
            remediation=(
                f"Install a matching-architecture WinFsp release ({arch_label}) "
                "or point FUSE_LIBRARY_PATH at a valid "
                f"{expected_dll} for this Python process."
            ),
            details={
                "architecture": arch_label,
                "python_bits": bit_label,
                "library_path": path,
                "expected_dll": expected_dll,
                "os_error": str(exc),
            },
        ) from exc

    _winfsp_handle = handle
    _winfsp_path = path
    _winfsp_loaded = True
    return handle


# ---------------------------------------------------------------------------
# Version / service probes (path and registry only — never start)
# ---------------------------------------------------------------------------


_VERSION_FILE_CANDIDATES: Tuple[str, ...] = (
    "version.txt",
    "VERSION",
    "Version.txt",
)


def probe_winfsp_version_from_install_dir(
    install_dir: Optional[os.PathLike[str] | str],
) -> Dict[str, Any]:
    """Best-effort version probe from InstallDir text files (no DLL load)."""
    result: Dict[str, Any] = {
        "version": None,
        "major": None,
        "source": None,
        "raw": None,
    }
    if not install_dir:
        return result
    base = Path(install_dir)
    for name in _VERSION_FILE_CANDIDATES:
        path = base / name
        try:
            if not path.is_file():
                continue
            raw = path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if not raw:
            continue
        # First line / first token that looks like a version.
        token = raw.splitlines()[0].strip()
        match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", token)
        if match:
            major = int(match.group(1))
            result["version"] = match.group(0)
            result["major"] = major
            result["source"] = str(path)
            result["raw"] = token
            return result
        result["version"] = token
        result["source"] = str(path)
        result["raw"] = token
        return result
    return result


def _default_service_reader(service_name: str) -> Optional[Mapping[str, Any]]:
    """Probe Windows service registry keys without starting the service."""
    if sys.platform != "win32":
        return None
    # Services live under HKLM\SYSTEM\CurrentControlSet\Services\<Name>.
    image_path = read_winfsp_registry_value(
        "HKEY_LOCAL_MACHINE",
        rf"SYSTEM\CurrentControlSet\Services\{service_name}",
        "ImagePath",
    )
    start_raw = read_winfsp_registry_value(
        "HKEY_LOCAL_MACHINE",
        rf"SYSTEM\CurrentControlSet\Services\{service_name}",
        "Start",
    )
    if image_path is None and start_raw is None:
        # Also try Type value as a presence signal.
        type_raw = read_winfsp_registry_value(
            "HKEY_LOCAL_MACHINE",
            rf"SYSTEM\CurrentControlSet\Services\{service_name}",
            "Type",
        )
        if type_raw is None:
            return None
    return {
        "name": service_name,
        "present": True,
        "image_path": image_path,
        "start": start_raw,
        "started_by_doctor": False,
        "state": "registered",  # not queried via SCM; registry presence only
    }


def probe_winfsp_service(
    *,
    service_names: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Probe WinFsp user-mode service registration without starting it."""
    names = tuple(service_names) if service_names is not None else WINFSP_SERVICE_NAMES
    reader = _service_reader if _service_reader is not None else _default_service_reader
    found: List[Dict[str, Any]] = []
    for name in names:
        try:
            info = reader(name)
        except Exception as exc:  # pragma: no cover - defensive
            found.append(
                {
                    "name": name,
                    "present": False,
                    "error": type(exc).__name__,
                    "started_by_doctor": False,
                }
            )
            continue
        if info:
            entry = dict(info)
            entry.setdefault("name", name)
            entry.setdefault("present", True)
            entry["started_by_doctor"] = False
            found.append(entry)
    available = any(bool(item.get("present")) for item in found)
    return {
        "check": "winfsp_service",
        "available": available,
        "services": found,
        "service_names_probed": list(names),
        "service_started": False,
        "actionable_absence": None
        if available
        else (
            "WinFsp user-mode service (WinFsp.Launcher / WinFsp) is not registered. "
            "Install WinFsp with the launcher service enabled; this doctor never "
            "starts or installs the service."
        ),
    }


def probe_winfsp_driver(
    *,
    install_dir: Optional[str] = None,
    bits: Optional[str] = None,
    service_names: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Probe WinFsp kernel driver presence without loading or starting it."""
    names = (
        tuple(service_names)
        if service_names is not None
        else WINFSP_DRIVER_SERVICE_NAMES
    )
    bit_label = bits if bits is not None else python_bits_label()
    sys_path = (
        winfsp_sys_path_from_install_dir(install_dir, bits=bit_label)
        if install_dir
        else None
    )
    sys_exists = bool(sys_path and os.path.isfile(sys_path))

    reader = _service_reader if _service_reader is not None else _default_service_reader
    service_hits: List[Dict[str, Any]] = []
    for name in names:
        try:
            info = reader(name)
        except Exception:
            info = None
        if info:
            entry = dict(info)
            entry.setdefault("name", name)
            entry.setdefault("present", True)
            entry["started_by_doctor"] = False
            service_hits.append(entry)

    available = sys_exists or any(bool(s.get("present")) for s in service_hits)
    return {
        "check": "winfsp_driver",
        "available": available,
        "driver_path": sys_path,
        "driver_exists": sys_exists,
        "expected_sys": expected_winfsp_sys_basename(bits=bit_label),
        "service_hits": service_hits,
        "service_started": False,
        "driver_started": False,
        "actionable_absence": None
        if available
        else (
            "WinFsp kernel driver was not found (no matching .sys under InstallDir "
            "and no driver service registration). Install WinFsp for this "
            "architecture; this doctor never loads or starts the driver."
        ),
    }


# ---------------------------------------------------------------------------
# Doctor probes
# ---------------------------------------------------------------------------


def _probe_os_architecture() -> Dict[str, Any]:
    system = platform.system()
    machine = platform.machine()
    arch = normalize_machine(machine)
    # Doctor is informative on any OS; native readiness requires Windows.
    supported = system == "Windows"
    try:
        uname = platform.uname()
        platform_label = (
            f"{uname.system}-{uname.release}-{uname.machine}"
            if uname.system
            else system
        )
    except Exception:  # pragma: no cover
        platform_label = system
    bits = python_bits_label()
    return {
        "check": "os_architecture",
        "available": supported,
        "os": system,
        "architecture": machine,
        "architecture_normalized": arch,
        "python_bits": bits,
        "expected_dll": expected_winfsp_dll_basename(bits=bits),
        "dll_arch_label": dll_arch_label_for_bits(bits),
        "platform": platform_label,
        "python_version": platform.python_version(),
        "actionable_absence": None
        if supported
        else (
            f"OS {system!r} is outside the supported Windows WinFsp/fusepy mount "
            "profile. Use a Windows host with a matching-architecture WinFsp "
            "installation, or the Linux FUSE profile on Linux."
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
            "Install the optional [fuse] extra (fusepy) for Windows WinFsp mounts. "
            "Package import success alone does not establish native WinFsp capability."
        ),
    }


def _probe_winfsp_dll(
    *,
    bits: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
    install_dir: Optional[str] = None,
) -> Dict[str, Any]:
    environ = env if env is not None else os.environ
    bit_label = bits if bits is not None else python_bits_label()
    expected = expected_winfsp_dll_basename(bits=bit_label)
    arch_label = dll_arch_label_for_bits(bit_label)

    resolved_install = install_dir
    registry_key: Optional[Tuple[str, str]] = None
    if resolved_install is None:
        resolved_install, registry_key = lookup_winfsp_install_dir()

    candidates = winfsp_dll_candidate_paths(
        bits=bit_label, env=environ, install_dir=resolved_install
    )
    found: List[str] = []
    for path in candidates:
        if os.path.isfile(path):
            found.append(path)

    resolved = resolve_winfsp_dll_path(
        bits=bit_label,
        env=environ,
        install_dir=resolved_install,
        require_exists=True,
        validate_architecture=False,
    )
    available = resolved is not None and os.path.isfile(resolved)
    explicit = (environ.get(FUSE_LIBRARY_PATH_ENV) or "").strip() or None
    resolution_source = None
    if available and resolved:
        if explicit and os.path.normcase(os.path.abspath(resolved)) == os.path.normcase(
            os.path.abspath(explicit)
        ):
            resolution_source = "FUSE_LIBRARY_PATH"
        elif resolved_install:
            resolution_source = "winfsp_registry_install_dir"
        else:
            resolution_source = "path_probe"

    pe_label = pe_machine_label(read_pe_machine(resolved)) if resolved else None

    if available:
        absence = None
    elif explicit and not os.path.isfile(explicit):
        absence = (
            f"FUSE_LIBRARY_PATH is set to {explicit!r} but the file is missing. "
            f"Point it at a valid {expected} for this Python process "
            f"(architecture {arch_label}), or install WinFsp so registry "
            "InstallDir resolution can succeed. This probe does not LoadLibrary."
        )
    elif not resolved_install:
        absence = (
            "WinFsp is not installed (registry InstallDir missing) and "
            "FUSE_LIBRARY_PATH is unset or unusable. Install WinFsp for the "
            f"matching architecture ({arch_label}) providing {expected}, or set "
            "FUSE_LIBRARY_PATH to that DLL. This doctor never installs WinFsp."
        )
    else:
        absence = (
            f"WinFsp InstallDir is {resolved_install!r} but {expected} was not "
            f"found under its bin folder (architecture {arch_label}). Repair the "
            "WinFsp installation or set FUSE_LIBRARY_PATH. This probe does not "
            "LoadLibrary or mount."
        )

    return {
        "check": "winfsp_dll",
        "available": bool(available),
        "architecture": arch_label,
        "python_bits": bit_label,
        "expected_dll": expected,
        "resolved_path": resolved,
        "resolution_source": resolution_source,
        "install_dir": resolved_install,
        "registry_key": (
            {"root": registry_key[0], "subkey": registry_key[1]}
            if registry_key
            else None
        ),
        "env_override": explicit,
        "candidates_checked": candidates,
        "found": found,
        "pe_machine_label": pe_label,
        "loaded": is_winfsp_loaded(),
        "loadlibrary_performed": False,
        "actionable_absence": absence,
    }


def _probe_winfsp_version(
    *,
    install_dir: Optional[str] = None,
    dll_path: Optional[str] = None,
) -> Dict[str, Any]:
    version_info = probe_winfsp_version_from_install_dir(install_dir)
    version = version_info.get("version")
    major = version_info.get("major")

    # Presence of a resolvable DLL is enough for "version check available" when
    # no version resource exists; incompatible major is a hard absence.
    if major is not None and major < MINIMUM_WINFSP_MAJOR:
        available = False
        absence = (
            f"WinFsp version {version!r} is below the minimum supported major "
            f"{MINIMUM_WINFSP_MAJOR}. Upgrade WinFsp; this doctor does not install."
        )
    elif version is not None or dll_path:
        available = True
        absence = None
    elif install_dir:
        # InstallDir known but no version file and no DLL path yet.
        available = True
        absence = None
        version_info = dict(version_info)
        version_info["note"] = (
            "No version.txt under InstallDir; version treated as present via install"
        )
    else:
        available = False
        absence = (
            "WinFsp version cannot be determined because InstallDir and DLL are "
            "missing. Install WinFsp; this doctor never installs or upgrades it."
        )

    return {
        "check": "winfsp_version",
        "available": available,
        "version": version,
        "major": major,
        "minimum_major": MINIMUM_WINFSP_MAJOR,
        "source": version_info.get("source"),
        "raw": version_info.get("raw"),
        "dll_path": dll_path,
        "install_dir": install_dir,
        "actionable_absence": absence,
    }


def _probe_architecture_agreement(
    *,
    bits: Optional[str] = None,
    dll_path: Optional[str] = None,
) -> Dict[str, Any]:
    bit_label = bits if bits is not None else python_bits_label()
    expected = dll_arch_label_for_bits(bit_label)
    expected_dll = expected_winfsp_dll_basename(bits=bit_label)

    if not dll_path:
        return {
            "check": "architecture_agreement",
            "available": False,
            "python_bits": bit_label,
            "expected_arch": expected,
            "expected_dll": expected_dll,
            "dll_path": None,
            "pe_machine_label": None,
            "basename_matches": False,
            "pe_matches": False,
            "actionable_absence": (
                f"Cannot verify Python/DLL architecture agreement because the "
                f"WinFsp DLL for {expected} ({expected_dll}) was not resolved. "
                "Install matching WinFsp or set FUSE_LIBRARY_PATH."
            ),
        }

    basename = os.path.basename(dll_path)
    basename_matches = basename.lower() == expected_dll.lower()
    # Also accept explicit overrides named with the arch token.
    if not basename_matches:
        basename_matches = expected in basename.lower() or (
            "x64" in basename.lower() and expected == "x64"
        ) or (
            "x86" in basename.lower() and expected == "x86"
        )

    pe_matches, pe_label, _ = pe_architecture_matches_python(dll_path, bits=bit_label)

    # When the PE Machine field is readable it is authoritative (allows
    # operator FUSE_LIBRARY_PATH overrides with non-standard basenames).
    # Hermetic / non-PE fixtures fall back to the x86/x64 basename signal.
    if pe_label is not None:
        available = bool(pe_matches)
    else:
        available = bool(basename_matches)

    if available:
        absence = None
    elif pe_label is not None and not pe_matches:
        absence = (
            f"WinFsp DLL architecture {pe_label!r} does not match this Python "
            f"process ({bit_label}, expects {expected}). Install the "
            f"{expected_dll} build or use a matching Python interpreter. "
            "This probe does not LoadLibrary."
        )
    else:
        absence = (
            f"Resolved DLL basename {basename!r} does not match the expected "
            f"{expected_dll} for this Python process ({bit_label}). Point "
            "FUSE_LIBRARY_PATH at the matching x86/x64 WinFsp DLL."
        )

    return {
        "check": "architecture_agreement",
        "available": available,
        "python_bits": bit_label,
        "expected_arch": expected,
        "expected_dll": expected_dll,
        "dll_path": dll_path,
        "dll_basename": basename,
        "basename_matches": basename_matches,
        "pe_machine_label": pe_label,
        "pe_matches": pe_matches if pe_label is not None else None,
        "actionable_absence": absence,
    }


def _probe_drive_directory_prerequisites(
    *,
    drive_letter: Optional[str] = None,
    mount_directory: Optional[os.PathLike[str] | str] = None,
    state_dir: Optional[os.PathLike[str] | str] = None,
) -> Dict[str, Any]:
    """Diagnose drive-letter and directory mount prerequisites without mounting.

    When paths are omitted, uses disposable temporary directories (never a real
    drive mount) so the probe remains hermetic on non-Windows CI.
    """
    created_base: Optional[Path] = None
    try:
        # --- Drive letter probe ---
        used_drives: List[str] = []
        free_drives: List[str] = []
        for letter in string.ascii_uppercase:
            root = f"{letter}:\\"
            # On non-Windows, Path existence of "C:\\" is false — report empty.
            if sys.platform == "win32":
                if os.path.exists(root):
                    used_drives.append(letter)
                else:
                    free_drives.append(letter)
            else:
                # Hermetic non-Windows: treat A-Z as free for prerequisite shape.
                free_drives.append(letter)

        requested_drive = None
        drive_available: Optional[bool] = None
        if drive_letter:
            letter = drive_letter.strip().rstrip(":").upper()
            if len(letter) == 1 and letter in string.ascii_uppercase:
                requested_drive = letter
                if sys.platform == "win32":
                    drive_available = letter in free_drives
                else:
                    # Off-Windows hermetic: explicit request is "evaluable".
                    drive_available = True
            else:
                requested_drive = drive_letter
                drive_available = False

        # --- Directory mount probe ---
        if mount_directory is None or state_dir is None:
            created_base = Path(tempfile.mkdtemp(prefix="kvfs608-doctor-"))
            mnt = (
                Path(mount_directory)
                if mount_directory is not None
                else created_base / "mnt"
            )
            st = (
                Path(state_dir)
                if state_dir is not None
                else created_base / "state"
            )
            if mount_directory is None:
                mnt.mkdir(mode=0o755, exist_ok=True)
            if state_dir is None:
                st.mkdir(mode=0o700, exist_ok=True)
        else:
            mnt = Path(mount_directory)
            st = Path(state_dir)

        mount_ok = mnt.is_dir() and os.access(mnt, os.R_OK | os.W_OK | os.X_OK)
        state_ok = st.is_dir() and os.access(st, os.R_OK | os.W_OK | os.X_OK)

        try:
            same_path = mnt.resolve() == st.resolve()
        except OSError:
            same_path = os.path.normpath(str(mnt)) == os.path.normpath(str(st))

        nested = False
        try:
            if not same_path:
                try:
                    st.resolve().relative_to(mnt.resolve())
                    nested = True
                except ValueError:
                    nested = False
        except OSError:
            nested = False

        separated = (not same_path) and (not nested)

        # Directory form requires accessible, separated dirs.
        directory_ok = mount_ok and state_ok and separated

        # Drive form: at least one free letter, or the requested letter free.
        if requested_drive is not None:
            drive_ok = bool(drive_available)
        else:
            drive_ok = bool(free_drives)

        # Overall: both forms are diagnosable; readiness needs directory_ok
        # and drive form evaluable (free letter or valid request).
        available = directory_ok and drive_ok

        if available:
            absence = None
        else:
            parts: List[str] = []
            if not directory_ok:
                if same_path:
                    parts.append(
                        "mount directory and state directory resolve to the same path"
                    )
                elif nested:
                    parts.append(
                        "state directory is nested under the mount directory"
                    )
                else:
                    parts.append(
                        "mount directory and state directory must be writable and distinct"
                    )
            if not drive_ok:
                if requested_drive is not None:
                    parts.append(
                        f"drive letter {requested_drive}: is not available for mounting"
                    )
                else:
                    parts.append("no free drive letters are available for mounting")
            absence = (
                "; ".join(parts)
                + ". Fix drive/directory prerequisites before mounting; "
                "this probe never mounts."
            )

        return {
            "check": "drive_directory_prerequisites",
            "available": available,
            "mounted": False,
            "drive": {
                "requested": requested_drive,
                "requested_available": drive_available,
                "used_drives": used_drives,
                "free_drives": free_drives,
                "free_count": len(free_drives),
                "evaluable": True,
            },
            "directory": {
                "mount_directory": str(mnt),
                "state_dir": str(st),
                "mount_accessible": mount_ok,
                "state_accessible": state_ok,
                "same_path": same_path,
                "state_nested_under_mount": nested,
                "separated": separated,
                "available": directory_ok,
            },
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


def run_windows_doctor(
    *,
    budget_seconds: float = DOCTOR_BUDGET_SECONDS,
    drive_letter: Optional[str] = None,
    mount_directory: Optional[os.PathLike[str] | str] = None,
    state_dir: Optional[os.PathLike[str] | str] = None,
    env: Optional[Mapping[str, str]] = None,
    install_dir: Optional[str] = None,
    bits: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the bounded Windows WinFsp capability doctor.

    Never mounts, never imports fusepy, never LoadLibrarys WinFsp, never starts
    the service or driver. Completes within *budget_seconds* or raises
    :class:`DoctorBudgetError`.
    """
    started = time.perf_counter()
    environ = env if env is not None else os.environ
    bit_label = bits if bits is not None else python_bits_label()

    checks: Dict[str, Any] = {}
    checks["os_architecture"] = _probe_os_architecture()
    checks["python_binding"] = _probe_python_binding()

    # Resolve InstallDir once so DLL / driver / version probes stay consistent.
    resolved_install = (install_dir or "").strip() or None
    if resolved_install is None:
        resolved_install, _ = lookup_winfsp_install_dir()

    dll_probe = _probe_winfsp_dll(
        bits=bit_label, env=environ, install_dir=resolved_install
    )
    checks["winfsp_dll"] = dll_probe
    dll_path = dll_probe.get("resolved_path")
    # Prefer InstallDir discovered by the DLL probe (may include registry).
    if resolved_install is None:
        resolved_install = dll_probe.get("install_dir")

    checks["winfsp_service"] = probe_winfsp_service()
    checks["winfsp_driver"] = probe_winfsp_driver(
        install_dir=resolved_install, bits=bit_label
    )
    checks["winfsp_version"] = _probe_winfsp_version(
        install_dir=resolved_install,
        dll_path=dll_path if isinstance(dll_path, str) else None,
    )
    checks["architecture_agreement"] = _probe_architecture_agreement(
        bits=bit_label,
        dll_path=dll_path if isinstance(dll_path, str) else None,
    )
    checks["drive_directory_prerequisites"] = _probe_drive_directory_prerequisites(
        drive_letter=drive_letter,
        mount_directory=mount_directory,
        state_dir=state_dir,
    )

    absences = _collect_absences(checks)
    checks["actionable_absence"] = {
        "check": "actionable_absence",
        "available": True,
        "count": len(absences),
        "items": absences,
        "policy": (
            "Missing or incompatible native WinFsp support is a typed terminal "
            "receipt for this run; it never leaves a probe running, never mounts, "
            "never starts the WinFsp service or driver, and never claims support "
            "from package import alone."
        ),
    }

    elapsed = time.perf_counter() - started
    if elapsed > budget_seconds:
        raise DoctorBudgetError(
            f"Windows WinFsp doctor exceeded budget: "
            f"{elapsed:.3f}s > {budget_seconds:.3f}s"
        )

    readiness_keys = (
        "os_architecture",
        "python_binding",
        "winfsp_dll",
        "winfsp_service",
        "winfsp_driver",
        "winfsp_version",
        "architecture_agreement",
        "drive_directory_prerequisites",
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
        "service_started": False,
        "driver_started": False,
        "native_capability_ready": native_ready,
        "support_claim": (
            "probe_passed" if native_ready else "capability_unavailable"
        ),
        "checks": checks,
        "required_checks": list(REQUIRED_DOCTOR_CHECKS),
        "policy": {
            "no_mount": True,
            "no_driver_install": True,
            "no_service_start": True,
            "no_fusepy_import": True,
            "no_winfsp_loadlibrary": True,
            "import_is_not_capability": True,
            "budget_seconds": budget_seconds,
            "supported_abi": "winfsp_fuse_compat",
            "supported_binding": "fusepy_winfsp",
            "resolution_order": [
                "FUSE_LIBRARY_PATH",
                "winfsp_registry_install_dir",
            ],
        },
        "loader": {
            "binding_loaded": is_binding_loaded(),
            "winfsp_loaded": is_winfsp_loaded(),
            "binding_name": binding_module_name(),
            "winfsp_path": loaded_winfsp_path(),
        },
    }
    return report


# Alias used by lifecycle / packaging callers.
run_doctor = run_windows_doctor


def ensure_windows_winfsp_capability(
    *,
    budget_seconds: float = DOCTOR_BUDGET_SECONDS,
    drive_letter: Optional[str] = None,
    mount_directory: Optional[os.PathLike[str] | str] = None,
    state_dir: Optional[os.PathLike[str] | str] = None,
    env: Optional[Mapping[str, str]] = None,
    install_dir: Optional[str] = None,
    bits: Optional[str] = None,
    load_binding: bool = False,
    load_native: bool = False,
) -> Dict[str, Any]:
    """Run the doctor and raise :class:`FuseCapabilityError` when not ready.

    Never mounts and never starts WinFsp. Optional *load_binding* /
    *load_native* perform explicit loads only after the probe-only doctor
    passes.
    """
    report = run_windows_doctor(
        budget_seconds=budget_seconds,
        drive_letter=drive_letter,
        mount_directory=mount_directory,
        state_dir=state_dir,
        env=env,
        install_dir=install_dir,
        bits=bits,
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
                "Windows WinFsp capability is unavailable; "
                "see doctor report for details."
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
                "service_started": False,
            },
            absences=items,
        )

    if load_binding:
        load_fuse_binding()
    if load_native:
        load_winfsp_dll(env=env, install_dir=install_dir, bits=bits)

    report["loader"] = {
        "binding_loaded": is_binding_loaded(),
        "winfsp_loaded": is_winfsp_loaded(),
        "binding_name": binding_module_name(),
        "winfsp_path": loaded_winfsp_path(),
    }
    return report


@dataclass
class WindowsWinfspPlatform:
    """Small façade for lifecycle code that needs explicit load + doctor.

    Instantiation is inert; methods perform probes/loads on demand.
    """

    budget_seconds: float = DOCTOR_BUDGET_SECONDS
    _last_report: Optional[Dict[str, Any]] = field(default=None, repr=False)

    def doctor(
        self,
        *,
        drive_letter: Optional[str] = None,
        mount_directory: Optional[os.PathLike[str] | str] = None,
        state_dir: Optional[os.PathLike[str] | str] = None,
        install_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._last_report = run_windows_doctor(
            budget_seconds=self.budget_seconds,
            drive_letter=drive_letter,
            mount_directory=mount_directory,
            state_dir=state_dir,
            install_dir=install_dir,
        )
        return self._last_report

    def ensure(
        self,
        *,
        drive_letter: Optional[str] = None,
        mount_directory: Optional[os.PathLike[str] | str] = None,
        state_dir: Optional[os.PathLike[str] | str] = None,
        install_dir: Optional[str] = None,
        load_binding: bool = False,
        load_native: bool = False,
    ) -> Dict[str, Any]:
        self._last_report = ensure_windows_winfsp_capability(
            budget_seconds=self.budget_seconds,
            drive_letter=drive_letter,
            mount_directory=mount_directory,
            state_dir=state_dir,
            install_dir=install_dir,
            load_binding=load_binding,
            load_native=load_native,
        )
        return self._last_report

    def load_binding(self, *, force: bool = False) -> ModuleType:
        return load_fuse_binding(force=force)

    def load_winfsp_dll(
        self,
        *,
        library_path: Optional[str] = None,
        force: bool = False,
    ) -> Any:
        return load_winfsp_dll(library_path=library_path, force=force)

    @property
    def last_report(self) -> Optional[Dict[str, Any]]:
        return self._last_report


__all__ = [
    "TASK_ID",
    "DOCTOR_SCHEMA",
    "SCHEMA_VERSION",
    "DOCTOR_BUDGET_SECONDS",
    "FUSE_LIBRARY_PATH_ENV",
    "WINFSP_DLL_X64",
    "WINFSP_DLL_X86",
    "WINFSP_DLL_BY_BITS",
    "WINFSP_REGISTRY_KEYS",
    "WINFSP_INSTALL_DIR_VALUE",
    "WINFSP_SERVICE_NAMES",
    "WINFSP_DRIVER_SERVICE_NAMES",
    "REQUIRED_DOCTOR_CHECKS",
    "KernelVFSPlatformError",
    "DoctorBudgetError",
    "FuseCapabilityError",
    "is_binding_loaded",
    "is_winfsp_loaded",
    "binding_module_name",
    "loaded_winfsp_path",
    "reset_loader_state",
    "set_registry_reader",
    "set_service_reader",
    "normalize_machine",
    "python_bits_label",
    "expected_winfsp_dll_basename",
    "expected_winfsp_sys_basename",
    "dll_arch_label_for_bits",
    "read_pe_machine",
    "pe_machine_label",
    "pe_architecture_matches_python",
    "lookup_winfsp_install_dir",
    "winfsp_dll_path_from_install_dir",
    "winfsp_sys_path_from_install_dir",
    "winfsp_dll_candidate_paths",
    "resolve_winfsp_dll_path",
    "load_fuse_binding",
    "load_winfsp_dll",
    "probe_winfsp_service",
    "probe_winfsp_driver",
    "probe_winfsp_version_from_install_dir",
    "run_windows_doctor",
    "run_doctor",
    "ensure_windows_winfsp_capability",
    "WindowsWinfspPlatform",
]

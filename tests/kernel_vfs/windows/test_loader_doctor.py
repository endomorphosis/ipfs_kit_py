"""KVFS-608: deterministic WinFsp/fusepy loader and bounded Windows doctor.

Acceptance coverage:

* core import of ``kernel_vfs.winfsp_loader`` is inert (no fusepy import, no
  WinFsp LoadLibrary, no service start, no mount);
* explicit ``FUSE_LIBRARY_PATH`` then validated WinFsp registry lookup resolves
  the matching x86/x64 DLL;
* doctor diagnoses service/driver/DLL/version/architecture and drive/directory
  prerequisites within five seconds;
* missing or incompatible native support is typed and never mounts.
"""

from __future__ import annotations

import importlib
import struct
import sys
import time
import types
from pathlib import Path
from typing import List, Mapping, Optional

import pytest

# ---------------------------------------------------------------------------
# Import under test (must remain side-effect free)
# ---------------------------------------------------------------------------

# Capture fuse-related modules present before our import so inertness checks
# do not false-fail when the environment already imported them.
_PREEXISTING_FUSE_MODULES = {
    name for name in ("fuse", "fusepy") if name in sys.modules
}

from ipfs_kit_py.kernel_vfs import winfsp_loader as kvfs_winfsp  # noqa: E402


REQUIRED_DOCTOR_CHECKS = (
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


@pytest.fixture(autouse=True)
def _reset_loader_state():
    """Keep loader caches and injectors isolated across tests."""
    kvfs_winfsp.reset_loader_state()
    yield
    kvfs_winfsp.reset_loader_state()


# ---------------------------------------------------------------------------
# Helpers: fake PE DLL, registry, services
# ---------------------------------------------------------------------------


def _write_pe_dll(path: Path, *, machine: int) -> Path:
    """Write a minimal PE image with the given Machine field (no real code)."""
    # DOS header: MZ + e_lfanew at offset 60 pointing to 0x80.
    dos = bytearray(0x80)
    dos[0:2] = b"MZ"
    struct.pack_into("<I", dos, 60, 0x80)
    pe = bytearray()
    pe += b"PE\0\0"
    pe += struct.pack("<H", machine)  # Machine
    pe += struct.pack("<H", 0)  # NumberOfSections
    pe += struct.pack("<I", 0)  # TimeDateStamp
    pe += struct.pack("<I", 0)  # PointerToSymbolTable
    pe += struct.pack("<I", 0)  # NumberOfSymbols
    pe += struct.pack("<H", 0)  # SizeOfOptionalHeader
    pe += struct.pack("<H", 0)  # Characteristics
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(dos) + bytes(pe))
    return path


def _install_layout(
    root: Path,
    *,
    bits: str = "64bit",
    machine: Optional[int] = None,
    with_sys: bool = True,
    version: str = "2.0.23075",
) -> Path:
    """Create a fake WinFsp InstallDir with bin DLL (+ optional .sys)."""
    install = root / "WinFsp"
    bin_dir = install / "bin"
    bin_dir.mkdir(parents=True)
    dll_name = kvfs_winfsp.expected_winfsp_dll_basename(bits=bits)
    if machine is None:
        machine = (
            kvfs_winfsp._PE_MACHINE_AMD64
            if bits == "64bit"
            else kvfs_winfsp._PE_MACHINE_I386
        )
    _write_pe_dll(bin_dir / dll_name, machine=machine)
    if with_sys:
        sys_name = kvfs_winfsp.expected_winfsp_sys_basename(bits=bits)
        (bin_dir / sys_name).write_bytes(b"fake-sys")
    (install / "version.txt").write_text(version + "\n", encoding="utf-8")
    return install


def _registry_for_install(install_dir: Path):
    install_str = str(install_dir)

    def _reader(root_name: str, subkey: str, value_name: str) -> Optional[str]:
        if value_name == kvfs_winfsp.WINFSP_INSTALL_DIR_VALUE and "WinFsp" in subkey:
            return install_str
        return None

    return _reader


def _service_reader_present(*names: str):
    present = set(names)

    def _reader(service_name: str) -> Optional[Mapping[str, object]]:
        if service_name in present:
            return {
                "name": service_name,
                "present": True,
                "image_path": rf"C:\Program Files\WinFsp\bin\{service_name}.exe",
                "start": "2",
                "state": "registered",
            }
        return None

    return _reader


# ---------------------------------------------------------------------------
# Core import is inert
# ---------------------------------------------------------------------------


def test_module_import_is_inert():
    """Importing winfsp_loader must not load fusepy or claim native handles."""
    assert kvfs_winfsp.is_binding_loaded() is False
    assert kvfs_winfsp.is_winfsp_loaded() is False
    assert kvfs_winfsp.binding_module_name() is None
    assert kvfs_winfsp.loaded_winfsp_path() is None

    for name in ("fuse", "fusepy"):
        if name not in _PREEXISTING_FUSE_MODULES:
            assert name not in sys.modules, f"import of winfsp_loader loaded {name}"


def test_import_does_not_loadlibrary_winfsp(monkeypatch):
    """ctypes.CDLL must not run as a side effect of import or doctor."""
    import ctypes

    def _boom(*_a, **_k):
        raise AssertionError("doctor/import must not LoadLibrary WinFsp")

    monkeypatch.setattr(ctypes, "CDLL", _boom)
    report = kvfs_winfsp.run_windows_doctor()
    assert report["mounted"] is False
    assert report["service_started"] is False
    assert report["policy"]["no_winfsp_loadlibrary"] is True
    assert report["checks"]["winfsp_dll"]["loadlibrary_performed"] is False
    assert kvfs_winfsp.is_winfsp_loaded() is False


def test_declared_output_module_path():
    module_file = Path(kvfs_winfsp.__file__).resolve()
    assert module_file.name == "winfsp_loader.py"
    assert module_file.parent.name == "kernel_vfs"
    assert "ipfs_kit_py" in module_file.parts


# ---------------------------------------------------------------------------
# Deterministic resolution: FUSE_LIBRARY_PATH then registry
# ---------------------------------------------------------------------------


def test_fuse_library_path_env_is_preferred(tmp_path):
    bits = "64bit"
    dll = tmp_path / kvfs_winfsp.expected_winfsp_dll_basename(bits=bits)
    dll.write_bytes(b"MZ-fake")
    env = {"FUSE_LIBRARY_PATH": str(dll)}

    # Even with a registry install, explicit env wins.
    install = _install_layout(tmp_path / "reg", bits=bits)
    kvfs_winfsp.set_registry_reader(_registry_for_install(install))

    resolved = kvfs_winfsp.resolve_winfsp_dll_path(bits=bits, env=env)
    assert resolved == str(dll)

    candidates = kvfs_winfsp.winfsp_dll_candidate_paths(bits=bits, env=env)
    assert candidates[0] == str(dll)


def test_registry_install_dir_resolves_matching_x64_dll(tmp_path):
    install = _install_layout(tmp_path, bits="64bit")
    kvfs_winfsp.set_registry_reader(_registry_for_install(install))

    resolved = kvfs_winfsp.resolve_winfsp_dll_path(bits="64bit", env={})
    assert resolved is not None
    assert resolved.endswith("winfsp-x64.dll")
    assert Path(resolved).is_file()
    assert str(install) in resolved


def test_registry_install_dir_resolves_matching_x86_dll(tmp_path):
    install = _install_layout(tmp_path, bits="32bit")
    kvfs_winfsp.set_registry_reader(_registry_for_install(install))

    resolved = kvfs_winfsp.resolve_winfsp_dll_path(bits="32bit", env={})
    assert resolved is not None
    assert resolved.endswith("winfsp-x86.dll")
    assert Path(resolved).is_file()


def test_x64_and_x86_candidates_differ(tmp_path):
    install = _install_layout(tmp_path, bits="64bit")
    # Also place x86 so both candidate paths exist.
    _write_pe_dll(
        install / "bin" / "winfsp-x86.dll",
        machine=kvfs_winfsp._PE_MACHINE_I386,
    )
    x64 = kvfs_winfsp.winfsp_dll_candidate_paths(
        bits="64bit", env={}, install_dir=str(install)
    )
    x86 = kvfs_winfsp.winfsp_dll_candidate_paths(
        bits="32bit", env={}, install_dir=str(install)
    )
    assert any(p.endswith("winfsp-x64.dll") for p in x64)
    assert any(p.endswith("winfsp-x86.dll") for p in x86)
    assert x64[0] != x86[0] or "winfsp-x64" in x64[0] or "winfsp-x86" in x86[0]
    # Primary install-dir candidates must select different basenames.
    assert kvfs_winfsp.winfsp_dll_path_from_install_dir(
        install, bits="64bit"
    ) != kvfs_winfsp.winfsp_dll_path_from_install_dir(install, bits="32bit")


def test_load_fuse_binding_is_explicit(monkeypatch):
    fake = types.ModuleType("fuse")
    fake.__kvfs_sentinel__ = "binding-ok"  # type: ignore[attr-defined]

    real_import_module = importlib.import_module

    def _import(name, package=None):
        if name in {"fuse", "fusepy"}:
            return fake
        return real_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", _import)
    assert kvfs_winfsp.is_binding_loaded() is False
    mod = kvfs_winfsp.load_fuse_binding()
    assert mod is fake
    assert kvfs_winfsp.is_binding_loaded() is True
    assert kvfs_winfsp.binding_module_name() in {"fuse", "fusepy"}
    assert kvfs_winfsp.load_fuse_binding() is fake


def test_load_fuse_binding_missing_raises_typed_error(monkeypatch):
    def _missing(name, package=None):
        raise ImportError(f"No module named {name!r}")

    monkeypatch.setattr(importlib, "import_module", _missing)
    with pytest.raises(kvfs_winfsp.FuseCapabilityError) as excinfo:
        kvfs_winfsp.load_fuse_binding(force=True)
    err = excinfo.value
    assert err.check == "python_binding"
    assert err.support_claim == "capability_unavailable"
    assert "fusepy" in err.remediation.lower() or "[fuse]" in err.remediation
    payload = err.to_dict()
    assert payload["mounted"] is False
    assert payload["service_started"] is False
    assert payload["support_claim"] == "capability_unavailable"


def test_load_winfsp_dll_is_explicit_and_architecture_aware(tmp_path, monkeypatch):
    bits = "64bit"
    install = _install_layout(tmp_path, bits=bits)
    dll_path = kvfs_winfsp.winfsp_dll_path_from_install_dir(install, bits=bits)

    calls: List[str] = []

    class _FakeDLL:
        def __init__(self, path):
            calls.append(path)
            self._path = path

    import ctypes

    monkeypatch.setattr(ctypes, "CDLL", _FakeDLL)
    kvfs_winfsp.set_registry_reader(_registry_for_install(install))

    assert kvfs_winfsp.is_winfsp_loaded() is False
    handle = kvfs_winfsp.load_winfsp_dll(bits=bits, env={})
    assert isinstance(handle, _FakeDLL)
    assert calls == [dll_path]
    assert kvfs_winfsp.is_winfsp_loaded() is True
    assert kvfs_winfsp.loaded_winfsp_path() == dll_path


def test_load_winfsp_dll_prefers_fuse_library_path(tmp_path, monkeypatch):
    bits = "64bit"
    install = _install_layout(tmp_path / "reg", bits=bits)
    kvfs_winfsp.set_registry_reader(_registry_for_install(install))

    override = tmp_path / "override" / "winfsp-x64.dll"
    override.parent.mkdir()
    override.write_bytes(b"MZ-override")

    calls: List[str] = []

    class _FakeDLL:
        def __init__(self, path):
            calls.append(path)

    import ctypes

    monkeypatch.setattr(ctypes, "CDLL", _FakeDLL)
    handle = kvfs_winfsp.load_winfsp_dll(
        bits=bits, env={"FUSE_LIBRARY_PATH": str(override)}
    )
    assert handle is not None
    assert calls == [str(override)]


def test_load_winfsp_dll_missing_raises_typed_error(monkeypatch):
    monkeypatch.setattr(
        kvfs_winfsp,
        "resolve_winfsp_dll_path",
        lambda **_k: None,
    )
    with pytest.raises(kvfs_winfsp.FuseCapabilityError) as excinfo:
        kvfs_winfsp.load_winfsp_dll(force=True)
    err = excinfo.value
    assert err.check == "winfsp_dll"
    assert "winfsp" in str(err).lower() or "winfsp" in err.remediation.lower()
    assert err.support_claim == "capability_unavailable"
    assert err.to_dict()["mounted"] is False


# ---------------------------------------------------------------------------
# PE architecture helpers
# ---------------------------------------------------------------------------


def test_read_pe_machine_x64_and_x86(tmp_path):
    x64 = _write_pe_dll(
        tmp_path / "winfsp-x64.dll", machine=kvfs_winfsp._PE_MACHINE_AMD64
    )
    x86 = _write_pe_dll(
        tmp_path / "winfsp-x86.dll", machine=kvfs_winfsp._PE_MACHINE_I386
    )
    assert kvfs_winfsp.read_pe_machine(x64) == kvfs_winfsp._PE_MACHINE_AMD64
    assert kvfs_winfsp.pe_machine_label(kvfs_winfsp.read_pe_machine(x64)) == "x64"
    assert kvfs_winfsp.read_pe_machine(x86) == kvfs_winfsp._PE_MACHINE_I386
    assert kvfs_winfsp.pe_machine_label(kvfs_winfsp.read_pe_machine(x86)) == "x86"

    matches, pe_label, expected = kvfs_winfsp.pe_architecture_matches_python(
        x64, bits="64bit"
    )
    assert matches is True
    assert pe_label == "x64"
    assert expected == "x64"

    matches, pe_label, expected = kvfs_winfsp.pe_architecture_matches_python(
        x86, bits="64bit"
    )
    assert matches is False
    assert pe_label == "x86"


# ---------------------------------------------------------------------------
# Doctor: bounds, checks, no mount / no fusepy import / no service start
# ---------------------------------------------------------------------------


def test_doctor_finishes_within_five_seconds_and_records_required_checks():
    started = time.perf_counter()
    report = kvfs_winfsp.run_windows_doctor()
    elapsed = time.perf_counter() - started

    assert elapsed < 5.0
    assert report["elapsed_seconds"] < 5.0
    assert report["within_budget"] is True
    assert report["budget_seconds"] == 5.0
    assert report["schema"] == kvfs_winfsp.DOCTOR_SCHEMA
    assert report["task_id"] == "KVFS-608"
    assert report["mounted"] is False
    assert report["service_started"] is False
    assert report["driver_started"] is False
    assert report["policy"]["no_mount"] is True
    assert report["policy"]["no_fusepy_import"] is True
    assert report["policy"]["no_winfsp_loadlibrary"] is True
    assert report["policy"]["no_service_start"] is True
    assert report["policy"]["no_driver_install"] is True
    assert report["policy"]["import_is_not_capability"] is True
    assert report["policy"]["supported_abi"] == "winfsp_fuse_compat"
    assert report["policy"]["resolution_order"][0] == "FUSE_LIBRARY_PATH"
    assert report["policy"]["resolution_order"][1] == "winfsp_registry_install_dir"

    for name in REQUIRED_DOCTOR_CHECKS:
        assert name in report["checks"], f"missing doctor check {name}"
        assert report["checks"][name]["check"] == name

    # Alias
    assert kvfs_winfsp.run_doctor is kvfs_winfsp.run_windows_doctor


def test_doctor_checks_service_driver_dll_version_arch_and_drive_directory(
    tmp_path,
):
    bits = "64bit"
    install = _install_layout(tmp_path, bits=bits)
    kvfs_winfsp.set_registry_reader(_registry_for_install(install))
    kvfs_winfsp.set_service_reader(
        _service_reader_present("WinFsp.Launcher", "WinFsp")
    )

    mnt = tmp_path / "mnt"
    state = tmp_path / "state"
    mnt.mkdir()
    state.mkdir()

    report = kvfs_winfsp.run_windows_doctor(
        bits=bits,
        env={},
        install_dir=str(install),
        mount_directory=mnt,
        state_dir=state,
        drive_letter="Z",
    )
    checks = report["checks"]

    binding = checks["python_binding"]
    assert binding["imported"] is False
    assert "fusepy_find_spec" in binding
    assert "fuse_module_find_spec" in binding

    dll = checks["winfsp_dll"]
    assert dll["loadlibrary_performed"] is False
    assert dll["expected_dll"] == "winfsp-x64.dll"
    assert dll["available"] is True
    assert dll["resolved_path"]
    assert dll["resolution_source"] in {
        "FUSE_LIBRARY_PATH",
        "winfsp_registry_install_dir",
        "path_probe",
    }

    svc = checks["winfsp_service"]
    assert svc["service_started"] is False
    assert svc["available"] is True

    drv = checks["winfsp_driver"]
    assert drv["driver_started"] is False
    assert drv["service_started"] is False
    assert drv["available"] is True
    assert drv["driver_exists"] is True

    ver = checks["winfsp_version"]
    assert ver["version"] is not None
    assert ver["available"] is True

    arch = checks["architecture_agreement"]
    assert arch["expected_arch"] == "x64"
    assert arch["available"] is True
    assert arch["pe_machine_label"] == "x64"

    drive = checks["drive_directory_prerequisites"]
    assert drive["mounted"] is False
    assert drive["directory"]["separated"] is True
    assert drive["directory"]["mount_directory"]
    assert drive["directory"]["state_dir"]
    assert "free_drives" in drive["drive"]


def test_doctor_does_not_import_fusepy(monkeypatch):
    real_import_module = importlib.import_module

    def _guarded(name, *args, **kwargs):
        if name in {"fusepy", "fuse"} or (
            isinstance(name, str) and name.startswith("fusepy.")
        ):
            raise AssertionError(f"doctor must not import {name}")
        return real_import_module(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", _guarded)

    import builtins

    real_import = builtins.__import__

    def _guarded_import(name, *args, **kwargs):
        if name in {"fusepy", "fuse"} or (
            isinstance(name, str) and name.startswith("fusepy.")
        ):
            raise AssertionError(f"doctor must not import {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _guarded_import)
    report = kvfs_winfsp.run_windows_doctor()
    assert report["checks"]["python_binding"]["imported"] is False
    assert report["mounted"] is False


def test_doctor_does_not_invoke_subprocess(monkeypatch):
    """Doctor must not shell out (service control, file utility, etc.)."""
    import subprocess

    def _boom(*_a, **_k):
        raise AssertionError("doctor must not invoke subprocess")

    monkeypatch.setattr(subprocess, "run", _boom)
    monkeypatch.setattr(subprocess, "call", _boom)
    monkeypatch.setattr(subprocess, "Popen", _boom)
    monkeypatch.setattr(subprocess, "check_output", _boom)
    monkeypatch.setattr(subprocess, "check_call", _boom)
    report = kvfs_winfsp.run_windows_doctor()
    assert report["mounted"] is False
    assert report["service_started"] is False
    bits = report["checks"]["os_architecture"]["python_bits"]
    assert bits in {"32bit", "64bit"}


def test_doctor_drive_directory_with_explicit_paths(tmp_path):
    mount_directory = tmp_path / "mnt"
    state_dir = tmp_path / "state"
    mount_directory.mkdir()
    state_dir.mkdir()

    report = kvfs_winfsp.run_windows_doctor(
        mount_directory=mount_directory, state_dir=state_dir
    )
    drive = report["checks"]["drive_directory_prerequisites"]
    assert drive["directory"]["separated"] is True
    assert drive["directory"]["same_path"] is False
    assert drive["mounted"] is False
    assert drive["directory"]["available"] is True


def test_doctor_rejects_colocated_mount_and_state(tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir()
    report = kvfs_winfsp.run_windows_doctor(
        mount_directory=shared, state_dir=shared
    )
    drive = report["checks"]["drive_directory_prerequisites"]
    assert drive["directory"]["separated"] is False
    assert drive["directory"]["same_path"] is True
    assert drive["available"] is False
    assert drive["actionable_absence"]
    assert report["native_capability_ready"] is False
    assert report["support_claim"] == "capability_unavailable"
    assert report["mounted"] is False


def test_doctor_rejects_state_nested_under_mount(tmp_path):
    mount_directory = tmp_path / "mnt"
    state_dir = mount_directory / "state"
    mount_directory.mkdir()
    state_dir.mkdir()
    report = kvfs_winfsp.run_windows_doctor(
        mount_directory=mount_directory, state_dir=state_dir
    )
    drive = report["checks"]["drive_directory_prerequisites"]
    assert drive["directory"]["separated"] is False
    assert drive["directory"]["state_nested_under_mount"] is True
    assert drive["available"] is False
    msg = (drive["actionable_absence"] or "").lower()
    assert "nested" in msg or "under" in msg


def test_doctor_architecture_mismatch_is_typed(tmp_path):
    """x86 DLL against 64-bit process fails architecture_agreement."""
    install = _install_layout(
        tmp_path,
        bits="32bit",  # writes winfsp-x86.dll
        machine=kvfs_winfsp._PE_MACHINE_I386,
    )
    # Force resolution of the x86 DLL while claiming 64-bit process via env path.
    dll = install / "bin" / "winfsp-x86.dll"
    report = kvfs_winfsp.run_windows_doctor(
        bits="64bit",
        env={"FUSE_LIBRARY_PATH": str(dll)},
        install_dir=str(install),
    )
    arch = report["checks"]["architecture_agreement"]
    assert arch["available"] is False
    assert arch["pe_machine_label"] == "x86"
    assert arch["expected_arch"] == "x64"
    assert arch["actionable_absence"]
    assert report["support_claim"] == "capability_unavailable"
    assert report["mounted"] is False


def test_doctor_absence_items_are_actionable_prose():
    report = kvfs_winfsp.run_windows_doctor()
    absence = report["checks"]["actionable_absence"]
    assert "items" in absence
    assert isinstance(absence["items"], list)
    for item in absence["items"]:
        assert item["check"]
        assert isinstance(item["message"], str) and len(item["message"]) > 20

    assert report["support_claim"] in {"capability_unavailable", "probe_passed"}
    if not report["native_capability_ready"]:
        assert report["support_claim"] == "capability_unavailable"
        assert absence["count"] >= 1


def test_doctor_with_full_fake_windows_stack_can_pass_non_os_checks(tmp_path, monkeypatch):
    """When OS is Windows and stack is complete, native readiness can pass.

    On Linux CI the os_architecture check remains unavailable; this test still
    verifies every other probe can light up under hermetic injectors.
    """
    bits = "64bit"
    install = _install_layout(tmp_path, bits=bits)
    kvfs_winfsp.set_registry_reader(_registry_for_install(install))
    kvfs_winfsp.set_service_reader(
        _service_reader_present("WinFsp.Launcher", "WinFsp")
    )

    # Pretend fusepy is present without importing it.
    real_find_spec = importlib.util.find_spec

    def _find_spec(name, package=None):
        if name in {"fuse", "fusepy"}:
            return types.SimpleNamespace(name=name)
        return real_find_spec(name, package)

    monkeypatch.setattr(importlib.util, "find_spec", _find_spec)

    mnt = tmp_path / "mnt"
    state = tmp_path / "state"
    mnt.mkdir()
    state.mkdir()

    report = kvfs_winfsp.run_windows_doctor(
        bits=bits,
        env={},
        install_dir=str(install),
        mount_directory=mnt,
        state_dir=state,
    )
    for name in (
        "python_binding",
        "winfsp_dll",
        "winfsp_service",
        "winfsp_driver",
        "winfsp_version",
        "architecture_agreement",
        "drive_directory_prerequisites",
    ):
        assert report["checks"][name]["available"] is True, name
    assert report["mounted"] is False
    assert report["service_started"] is False
    # On non-Windows hosts OS check fails closed.
    if sys.platform != "win32":
        assert report["checks"]["os_architecture"]["available"] is False
        assert report["native_capability_ready"] is False
        assert report["support_claim"] == "capability_unavailable"


# ---------------------------------------------------------------------------
# Typed capability error without mounting
# ---------------------------------------------------------------------------


def test_ensure_raises_typed_error_when_capability_missing(monkeypatch, tmp_path):
    """Absence must raise FuseCapabilityError and never mount or start service."""

    def _fake_doctor(**_kwargs):
        return {
            "schema": kvfs_winfsp.DOCTOR_SCHEMA,
            "schema_version": kvfs_winfsp.SCHEMA_VERSION,
            "task_id": "KVFS-608",
            "elapsed_seconds": 0.01,
            "budget_seconds": 5.0,
            "within_budget": True,
            "mounted": False,
            "service_started": False,
            "driver_started": False,
            "native_capability_ready": False,
            "support_claim": "capability_unavailable",
            "checks": {
                "actionable_absence": {
                    "check": "actionable_absence",
                    "available": True,
                    "count": 1,
                    "items": [
                        {
                            "check": "winfsp_dll",
                            "message": (
                                "WinFsp is not installed (registry InstallDir missing) "
                                "and FUSE_LIBRARY_PATH is unset or unusable. Install "
                                "WinFsp for the matching architecture. This doctor "
                                "never installs WinFsp."
                            ),
                        }
                    ],
                }
            },
            "required_checks": list(kvfs_winfsp.REQUIRED_DOCTOR_CHECKS),
            "policy": {"no_mount": True, "no_service_start": True},
            "loader": {
                "binding_loaded": False,
                "winfsp_loaded": False,
                "binding_name": None,
                "winfsp_path": None,
            },
        }

    monkeypatch.setattr(kvfs_winfsp, "run_windows_doctor", _fake_doctor)

    with pytest.raises(kvfs_winfsp.FuseCapabilityError) as excinfo:
        kvfs_winfsp.ensure_windows_winfsp_capability(
            mount_directory=tmp_path / "mnt",
            state_dir=tmp_path / "state",
        )
    err = excinfo.value
    assert isinstance(err, kvfs_winfsp.KernelVFSPlatformError)
    assert err.check == "winfsp_dll"
    assert err.support_claim == "capability_unavailable"
    assert "winfsp" in str(err).lower()
    assert err.to_dict()["mounted"] is False
    assert err.to_dict()["service_started"] is False
    assert kvfs_winfsp.is_binding_loaded() is False
    assert kvfs_winfsp.is_winfsp_loaded() is False


def test_ensure_raises_on_real_separation_failure(tmp_path):
    shared = tmp_path / "both"
    shared.mkdir()
    with pytest.raises(kvfs_winfsp.FuseCapabilityError) as excinfo:
        kvfs_winfsp.ensure_windows_winfsp_capability(
            mount_directory=shared, state_dir=shared
        )
    err = excinfo.value
    assert err.support_claim == "capability_unavailable"
    assert err.to_dict()["mounted"] is False
    checks_mentioned = {err.check} | {a["check"] for a in err.absences}
    assert (
        "drive_directory_prerequisites" in checks_mentioned
        or "os_architecture" in checks_mentioned
        or any(
            "same path" in a["message"].lower() or "distinct" in a["message"].lower()
            for a in err.absences
        )
    )


def test_ensure_passes_when_all_probes_ready(monkeypatch):
    ready_checks = {
        name: {"check": name, "available": True, "actionable_absence": None}
        for name in REQUIRED_DOCTOR_CHECKS
        if name != "actionable_absence"
    }
    ready_checks["actionable_absence"] = {
        "check": "actionable_absence",
        "available": True,
        "count": 0,
        "items": [],
    }

    def _ready(**_kwargs):
        return {
            "schema": kvfs_winfsp.DOCTOR_SCHEMA,
            "schema_version": kvfs_winfsp.SCHEMA_VERSION,
            "task_id": "KVFS-608",
            "elapsed_seconds": 0.01,
            "budget_seconds": 5.0,
            "within_budget": True,
            "mounted": False,
            "service_started": False,
            "driver_started": False,
            "native_capability_ready": True,
            "support_claim": "probe_passed",
            "checks": ready_checks,
            "required_checks": list(REQUIRED_DOCTOR_CHECKS),
            "policy": {"no_mount": True, "no_service_start": True},
            "loader": {
                "binding_loaded": False,
                "winfsp_loaded": False,
                "binding_name": None,
                "winfsp_path": None,
            },
        }

    monkeypatch.setattr(kvfs_winfsp, "run_windows_doctor", _ready)
    report = kvfs_winfsp.ensure_windows_winfsp_capability()
    assert report["native_capability_ready"] is True
    assert report["support_claim"] == "probe_passed"
    assert report["mounted"] is False
    assert report["service_started"] is False


def test_windows_winfsp_platform_facade_is_inert_until_used():
    facade = kvfs_winfsp.WindowsWinfspPlatform()
    assert facade.last_report is None
    assert kvfs_winfsp.is_binding_loaded() is False
    report = facade.doctor()
    assert report["mounted"] is False
    assert report["service_started"] is False
    assert facade.last_report is report


def test_doctor_budget_error_on_overrun(monkeypatch):
    clock = {"n": 0}

    def _clock() -> float:
        clock["n"] += 1
        return 0.0 if clock["n"] == 1 else 9.0

    monkeypatch.setattr(time, "perf_counter", _clock)
    with pytest.raises(kvfs_winfsp.DoctorBudgetError):
        kvfs_winfsp.run_windows_doctor(budget_seconds=0.5)


def test_normalize_machine_aliases():
    assert kvfs_winfsp.normalize_machine("AMD64") == "x86_64"
    assert kvfs_winfsp.normalize_machine("x64") == "x86_64"
    assert kvfs_winfsp.normalize_machine("x86") == "x86"
    assert kvfs_winfsp.normalize_machine("arm64") == "aarch64"


def test_required_doctor_checks_constant_matches_acceptance():
    for name in REQUIRED_DOCTOR_CHECKS:
        assert name in kvfs_winfsp.REQUIRED_DOCTOR_CHECKS
    assert "python_binding" in kvfs_winfsp.REQUIRED_DOCTOR_CHECKS
    assert "winfsp_dll" in kvfs_winfsp.REQUIRED_DOCTOR_CHECKS
    assert "winfsp_service" in kvfs_winfsp.REQUIRED_DOCTOR_CHECKS
    assert "winfsp_driver" in kvfs_winfsp.REQUIRED_DOCTOR_CHECKS
    assert "winfsp_version" in kvfs_winfsp.REQUIRED_DOCTOR_CHECKS
    assert "architecture_agreement" in kvfs_winfsp.REQUIRED_DOCTOR_CHECKS
    assert "drive_directory_prerequisites" in kvfs_winfsp.REQUIRED_DOCTOR_CHECKS


def test_dll_basename_helpers():
    assert kvfs_winfsp.expected_winfsp_dll_basename(bits="64bit") == "winfsp-x64.dll"
    assert kvfs_winfsp.expected_winfsp_dll_basename(bits="32bit") == "winfsp-x86.dll"
    assert kvfs_winfsp.dll_arch_label_for_bits("64bit") == "x64"
    assert kvfs_winfsp.dll_arch_label_for_bits("32bit") == "x86"

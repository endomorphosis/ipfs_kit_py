"""KVFS-503: lazy fusepy/libfuse loading and bounded Linux capability doctor.

Acceptance coverage:

* core import of ``kernel_vfs.platform`` is inert (no fusepy import, no
  libfuse dlopen, no mount);
* binding/native library load is explicit and architecture-aware;
* doctor checks fusepy, libfuse2 ABI, ``/dev/fuse``, fusermount helper,
  permissions, and mountpoint/state separation within five seconds;
* absence raises a typed, actionable capability error without mounting.
"""

from __future__ import annotations

import importlib
import sys
import time
import types
from pathlib import Path
from typing import List

import pytest

# ---------------------------------------------------------------------------
# Import under test (must remain side-effect free)
# ---------------------------------------------------------------------------

# Capture fuse-related modules present before our import so inertness checks
# do not false-fail when the environment already imported them.
_PREEXISTING_FUSE_MODULES = {
    name for name in ("fuse", "fusepy") if name in sys.modules
}

from ipfs_kit_py.kernel_vfs import platform as kvfs_platform  # noqa: E402


REQUIRED_DOCTOR_CHECKS = (
    "os_architecture",
    "python_binding",
    "libfuse2_abi",
    "dev_fuse",
    "fusermount_helper",
    "permissions",
    "mountpoint_state_separation",
    "actionable_absence",
)


@pytest.fixture(autouse=True)
def _reset_loader_state():
    """Keep loader caches isolated across tests."""
    kvfs_platform.reset_loader_state()
    yield
    kvfs_platform.reset_loader_state()


# ---------------------------------------------------------------------------
# Core import is inert
# ---------------------------------------------------------------------------


def test_module_import_is_inert():
    """Importing platform must not load fusepy or claim native handles."""
    assert kvfs_platform.is_binding_loaded() is False
    assert kvfs_platform.is_libfuse_loaded() is False
    assert kvfs_platform.binding_module_name() is None
    assert kvfs_platform.loaded_libfuse_path() is None

    # Import must not have introduced fuse modules that were not already present.
    for name in ("fuse", "fusepy"):
        if name not in _PREEXISTING_FUSE_MODULES:
            assert name not in sys.modules, f"import of platform loaded {name}"


def test_import_does_not_dlopen_libfuse(monkeypatch):
    """ctypes.CDLL must not run as a side effect of import or doctor."""
    import ctypes

    def _boom(*_a, **_k):
        raise AssertionError("doctor/import must not dlopen libfuse")

    monkeypatch.setattr(ctypes, "CDLL", _boom)
    # Re-import should stay inert; doctor must also avoid CDLL.
    report = kvfs_platform.run_linux_doctor()
    assert report["mounted"] is False
    assert report["policy"]["no_libfuse_dlopen"] is True
    assert report["checks"]["libfuse2_abi"]["dlopen_performed"] is False
    assert kvfs_platform.is_libfuse_loaded() is False


def test_declared_output_module_path():
    module_file = Path(kvfs_platform.__file__).resolve()
    assert module_file.name == "platform.py"
    assert module_file.parent.name == "kernel_vfs"
    assert "ipfs_kit_py" in module_file.parts


# ---------------------------------------------------------------------------
# Architecture-aware resolution (explicit load seam)
# ---------------------------------------------------------------------------


def test_libfuse2_candidates_are_architecture_aware():
    x86 = kvfs_platform.libfuse2_candidate_paths(machine="x86_64", env={})
    arm = kvfs_platform.libfuse2_candidate_paths(machine="aarch64", env={})

    assert any("x86_64-linux-gnu" in p for p in x86)
    assert any(p.endswith("libfuse.so.2") for p in x86)
    assert any("aarch64-linux-gnu" in p for p in arm)
    assert any(p.endswith("libfuse.so.2") for p in arm)
    # Architectures must not share the multiarch primary path.
    assert x86[0] != arm[0]


def test_fuse_library_path_env_is_preferred(tmp_path, monkeypatch):
    fake = tmp_path / "libfuse.so.2"
    fake.write_bytes(b"\x7fELF")  # not a real library; resolution is path-only
    env = {"FUSE_LIBRARY_PATH": str(fake)}
    resolved = kvfs_platform.resolve_libfuse2_path(machine="x86_64", env=env)
    assert resolved == str(fake)

    candidates = kvfs_platform.libfuse2_candidate_paths(machine="x86_64", env=env)
    assert candidates[0] == str(fake)


def test_load_fuse_binding_is_explicit(monkeypatch):
    """Binding load happens only through load_fuse_binding."""
    fake = types.ModuleType("fuse")
    fake.__kvfs_sentinel__ = "binding-ok"  # type: ignore[attr-defined]

    real_import_module = importlib.import_module

    def _import(name, package=None):
        if name in {"fuse", "fusepy"}:
            return fake
        return real_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", _import)
    assert kvfs_platform.is_binding_loaded() is False
    mod = kvfs_platform.load_fuse_binding()
    assert mod is fake
    assert kvfs_platform.is_binding_loaded() is True
    assert kvfs_platform.binding_module_name() in {"fuse", "fusepy"}
    # Cached on second call.
    assert kvfs_platform.load_fuse_binding() is fake


def test_load_fuse_binding_missing_raises_typed_error(monkeypatch):
    def _missing(name, package=None):
        raise ImportError(f"No module named {name!r}")

    monkeypatch.setattr(importlib, "import_module", _missing)
    with pytest.raises(kvfs_platform.FuseCapabilityError) as excinfo:
        kvfs_platform.load_fuse_binding(force=True)
    err = excinfo.value
    assert err.check == "python_binding"
    assert err.support_claim == "capability_unavailable"
    assert "fusepy" in err.remediation.lower() or "[fuse]" in err.remediation
    payload = err.to_dict()
    assert payload["mounted"] is False
    assert payload["support_claim"] == "capability_unavailable"


def test_load_libfuse2_is_explicit_and_architecture_aware(tmp_path, monkeypatch):
    """load_libfuse2 uses architecture resolution and only then CDLL."""
    fake_lib = tmp_path / "libfuse.so.2"
    fake_lib.write_bytes(b"\x7fELF-fake")

    calls: List[str] = []

    class _FakeDLL:
        def __init__(self, path):
            calls.append(path)
            self._path = path

    import ctypes

    monkeypatch.setattr(ctypes, "CDLL", _FakeDLL)
    monkeypatch.setenv("FUSE_LIBRARY_PATH", str(fake_lib))

    assert kvfs_platform.is_libfuse_loaded() is False
    handle = kvfs_platform.load_libfuse2(machine="x86_64")
    assert isinstance(handle, _FakeDLL)
    assert calls == [str(fake_lib)]
    assert kvfs_platform.is_libfuse_loaded() is True
    assert kvfs_platform.loaded_libfuse_path() == str(fake_lib)


def test_load_libfuse2_missing_raises_typed_error(monkeypatch):
    monkeypatch.setattr(
        kvfs_platform,
        "resolve_libfuse2_path",
        lambda **_k: None,
    )
    with pytest.raises(kvfs_platform.FuseCapabilityError) as excinfo:
        kvfs_platform.load_libfuse2(force=True)
    err = excinfo.value
    assert err.check == "libfuse2_abi"
    assert "libfuse2" in str(err).lower() or "libfuse" in err.remediation.lower()
    assert err.support_claim == "capability_unavailable"
    assert err.to_dict()["mounted"] is False


# ---------------------------------------------------------------------------
# Doctor: bounds, checks, no mount / no fusepy import
# ---------------------------------------------------------------------------


def test_doctor_finishes_within_five_seconds_and_records_required_checks():
    started = time.perf_counter()
    report = kvfs_platform.run_linux_doctor()
    elapsed = time.perf_counter() - started

    assert elapsed < 5.0
    assert report["elapsed_seconds"] < 5.0
    assert report["within_budget"] is True
    assert report["budget_seconds"] == 5.0
    assert report["schema"] == kvfs_platform.DOCTOR_SCHEMA
    assert report["task_id"] == "KVFS-503"
    assert report["mounted"] is False
    assert report["policy"]["no_mount"] is True
    assert report["policy"]["no_fusepy_import"] is True
    assert report["policy"]["no_libfuse_dlopen"] is True
    assert report["policy"]["import_is_not_capability"] is True
    assert report["policy"]["supported_abi"] == "libfuse2"

    for name in REQUIRED_DOCTOR_CHECKS:
        assert name in report["checks"], f"missing doctor check {name}"
        assert report["checks"][name]["check"] == name

    # Alias
    assert kvfs_platform.run_doctor is kvfs_platform.run_linux_doctor


def test_doctor_checks_fusepy_libfuse2_dev_fuse_helper_permissions_and_separation():
    report = kvfs_platform.run_linux_doctor()
    checks = report["checks"]

    binding = checks["python_binding"]
    assert binding["imported"] is False
    assert "fusepy_find_spec" in binding
    assert "fuse_module_find_spec" in binding

    abi = checks["libfuse2_abi"]
    assert abi["soname"] == "libfuse.so.2"
    assert abi["dlopen_performed"] is False
    assert "architecture" in abi
    assert isinstance(abi["candidates_checked"], list)

    dev = checks["dev_fuse"]
    assert dev["device"] == "/dev/fuse"
    assert "exists" in dev
    assert "accessible_rw" in dev

    helper = checks["fusermount_helper"]
    assert helper["invoked"] is False
    assert "helpers" in helper

    perms = checks["permissions"]
    assert "dev_fuse_accessible_rw" in perms

    sep = checks["mountpoint_state_separation"]
    assert sep["mounted"] is False
    assert "separated" in sep
    assert sep["mountpoint"]
    assert sep["state_dir"]


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
    report = kvfs_platform.run_linux_doctor()
    assert report["checks"]["python_binding"]["imported"] is False
    assert report["mounted"] is False


def test_doctor_does_not_invoke_fusermount(monkeypatch):
    """fusermount must only be located via which(), never executed.

    The doctor must not shell out at all — including via stdlib helpers such as
    ``platform.architecture()`` (which runs ``file``) or ``find_library``
    (which may run ``ldconfig``/``gcc``). Path/stat probes only.
    """
    import subprocess

    def _boom(*_a, **_k):
        raise AssertionError("doctor must not invoke subprocess for mount helpers")

    monkeypatch.setattr(subprocess, "run", _boom)
    monkeypatch.setattr(subprocess, "call", _boom)
    monkeypatch.setattr(subprocess, "Popen", _boom)
    monkeypatch.setattr(subprocess, "check_output", _boom)
    monkeypatch.setattr(subprocess, "check_call", _boom)
    report = kvfs_platform.run_linux_doctor()
    assert report["checks"]["fusermount_helper"]["invoked"] is False
    assert report["mounted"] is False
    # Architecture probe must stay pure-Python (no ``file`` utility).
    bits = report["checks"]["os_architecture"]["python_bits"]
    assert bits in {"32bit", "64bit"}


def test_doctor_mountpoint_state_separation_with_explicit_paths(tmp_path):
    mountpoint = tmp_path / "mnt"
    state_dir = tmp_path / "state"
    mountpoint.mkdir()
    state_dir.mkdir()

    report = kvfs_platform.run_linux_doctor(
        mountpoint=mountpoint, state_dir=state_dir
    )
    sep = report["checks"]["mountpoint_state_separation"]
    assert sep["separated"] is True
    assert sep["same_path"] is False
    assert sep["mounted"] is False
    assert sep["available"] is True


def test_doctor_rejects_colocated_mountpoint_and_state(tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir()
    report = kvfs_platform.run_linux_doctor(mountpoint=shared, state_dir=shared)
    sep = report["checks"]["mountpoint_state_separation"]
    assert sep["separated"] is False
    assert sep["same_path"] is True
    assert sep["available"] is False
    assert sep["actionable_absence"]
    assert report["native_capability_ready"] is False
    assert report["support_claim"] == "capability_unavailable"
    assert report["mounted"] is False


def test_doctor_rejects_state_nested_under_mountpoint(tmp_path):
    mountpoint = tmp_path / "mnt"
    state_dir = mountpoint / "state"
    mountpoint.mkdir()
    state_dir.mkdir()
    report = kvfs_platform.run_linux_doctor(
        mountpoint=mountpoint, state_dir=state_dir
    )
    sep = report["checks"]["mountpoint_state_separation"]
    assert sep["separated"] is False
    assert sep["state_nested_under_mountpoint"] is True
    assert sep["available"] is False
    assert "nested" in (sep["actionable_absence"] or "").lower() or "under" in (
        sep["actionable_absence"] or ""
    ).lower()


def test_doctor_absence_items_are_actionable_prose():
    report = kvfs_platform.run_linux_doctor()
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


# ---------------------------------------------------------------------------
# Typed capability error without mounting
# ---------------------------------------------------------------------------


def test_ensure_raises_typed_error_when_capability_missing(monkeypatch, tmp_path):
    """Absence must raise FuseCapabilityError and never mount."""

    def _fake_doctor(**_kwargs):
        return {
            "schema": kvfs_platform.DOCTOR_SCHEMA,
            "schema_version": kvfs_platform.SCHEMA_VERSION,
            "task_id": "KVFS-503",
            "elapsed_seconds": 0.01,
            "budget_seconds": 5.0,
            "within_budget": True,
            "mounted": False,
            "native_capability_ready": False,
            "support_claim": "capability_unavailable",
            "checks": {
                "actionable_absence": {
                    "check": "actionable_absence",
                    "available": True,
                    "count": 1,
                    "items": [
                        {
                            "check": "dev_fuse",
                            "message": (
                                "Kernel FUSE device /dev/fuse is missing. "
                                "Load the fuse module or expose the device. "
                                "This probe does not mount."
                            ),
                        }
                    ],
                }
            },
            "required_checks": list(kvfs_platform.REQUIRED_DOCTOR_CHECKS),
            "policy": {"no_mount": True},
            "loader": {
                "binding_loaded": False,
                "libfuse_loaded": False,
                "binding_name": None,
                "libfuse_path": None,
            },
        }

    monkeypatch.setattr(kvfs_platform, "run_linux_doctor", _fake_doctor)

    with pytest.raises(kvfs_platform.FuseCapabilityError) as excinfo:
        kvfs_platform.ensure_linux_fuse_capability(
            mountpoint=tmp_path / "mnt",
            state_dir=tmp_path / "state",
        )
    err = excinfo.value
    assert isinstance(err, kvfs_platform.KernelVFSPlatformError)
    assert err.check == "dev_fuse"
    assert err.support_claim == "capability_unavailable"
    assert "/dev/fuse" in str(err)
    assert err.to_dict()["mounted"] is False
    assert kvfs_platform.is_binding_loaded() is False
    assert kvfs_platform.is_libfuse_loaded() is False


def test_ensure_raises_on_real_separation_failure(tmp_path):
    shared = tmp_path / "both"
    shared.mkdir()
    with pytest.raises(kvfs_platform.FuseCapabilityError) as excinfo:
        kvfs_platform.ensure_linux_fuse_capability(
            mountpoint=shared, state_dir=shared
        )
    err = excinfo.value
    assert err.support_claim == "capability_unavailable"
    assert err.to_dict()["mounted"] is False
    # Separation failure should surface either as the primary check or in absences.
    checks_mentioned = {err.check} | {a["check"] for a in err.absences}
    assert "mountpoint_state_separation" in checks_mentioned or any(
        "same path" in a["message"].lower() or "distinct" in a["message"].lower()
        for a in err.absences
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
            "schema": kvfs_platform.DOCTOR_SCHEMA,
            "schema_version": kvfs_platform.SCHEMA_VERSION,
            "task_id": "KVFS-503",
            "elapsed_seconds": 0.01,
            "budget_seconds": 5.0,
            "within_budget": True,
            "mounted": False,
            "native_capability_ready": True,
            "support_claim": "probe_passed",
            "checks": ready_checks,
            "required_checks": list(REQUIRED_DOCTOR_CHECKS),
            "policy": {"no_mount": True},
            "loader": {
                "binding_loaded": False,
                "libfuse_loaded": False,
                "binding_name": None,
                "libfuse_path": None,
            },
        }

    monkeypatch.setattr(kvfs_platform, "run_linux_doctor", _ready)
    report = kvfs_platform.ensure_linux_fuse_capability()
    assert report["native_capability_ready"] is True
    assert report["support_claim"] == "probe_passed"
    assert report["mounted"] is False


def test_linux_fuse_platform_facade_is_inert_until_used():
    facade = kvfs_platform.LinuxFusePlatform()
    assert facade.last_report is None
    assert kvfs_platform.is_binding_loaded() is False
    report = facade.doctor()
    assert report["mounted"] is False
    assert facade.last_report is report


def test_doctor_budget_error_on_overrun(monkeypatch):
    # Force elapsed time past budget by patching perf_counter sequence.
    # Provide a long stream so incidental probe clocks cannot StopIteration.
    clock = {"n": 0}

    def _clock() -> float:
        clock["n"] += 1
        # First call is start (0.0); subsequent calls look like 9s later.
        return 0.0 if clock["n"] == 1 else 9.0

    monkeypatch.setattr(time, "perf_counter", _clock)
    with pytest.raises(kvfs_platform.DoctorBudgetError):
        kvfs_platform.run_linux_doctor(budget_seconds=0.5)


def test_normalize_machine_aliases():
    assert kvfs_platform.normalize_machine("AMD64") == "x86_64"
    assert kvfs_platform.normalize_machine("arm64") == "aarch64"
    assert kvfs_platform.normalize_machine("x86_64") == "x86_64"


def test_required_doctor_checks_constant_matches_acceptance():
    for name in REQUIRED_DOCTOR_CHECKS:
        assert name in kvfs_platform.REQUIRED_DOCTOR_CHECKS
    # Acceptance-named surfaces must be present.
    assert "python_binding" in kvfs_platform.REQUIRED_DOCTOR_CHECKS
    assert "libfuse2_abi" in kvfs_platform.REQUIRED_DOCTOR_CHECKS
    assert "dev_fuse" in kvfs_platform.REQUIRED_DOCTOR_CHECKS
    assert "fusermount_helper" in kvfs_platform.REQUIRED_DOCTOR_CHECKS
    assert "permissions" in kvfs_platform.REQUIRED_DOCTOR_CHECKS
    assert "mountpoint_state_separation" in kvfs_platform.REQUIRED_DOCTOR_CHECKS

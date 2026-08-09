"""KVFS-703: optional FUSE packaging, guarded imports, classifiers, wheel probes.

Acceptance coverage:

* default wheel / core import remains inert (no fusepy, no libfuse, no WinFsp);
* a pinned ``[fuse]`` extra installs the Python binding only;
* mount CLI is discoverable from packaging metadata;
* missing native driver/capability is diagnostic (typed doctor receipts);
* Python 3.12/3.13 × Linux/Windows wheel probes pass;
* Windows OS classifier is conditional on the live gate policy.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import subprocess
import sys
import textwrap
import tomllib
from pathlib import Path
from typing import Any, Mapping

import pytest

# tests/kernel_vfs/packaging -> parents[3] == package root (ipfs_kit_py/)
PACKAGE_ROOT = Path(__file__).resolve().parents[3]
PYPROJECT_PATH = PACKAGE_ROOT / "pyproject.toml"

TASK_ID = "KVFS-703"
WINDOWS_OS_CLASSIFIER = "Operating System :: Microsoft :: Windows"
FUSE_MODULE_NAMES = ("fuse", "fusepy")


# ---------------------------------------------------------------------------
# Metadata loaders
# ---------------------------------------------------------------------------


def _load_pyproject() -> dict[str, Any]:
    with PYPROJECT_PATH.open("rb") as handle:
        return tomllib.load(handle)


def _project() -> dict[str, Any]:
    return _load_pyproject()["project"]


def _packaging_policy() -> dict[str, Any]:
    tool = _load_pyproject().get("tool") or {}
    kit = tool.get("ipfs_kit_py") or {}
    kernel = kit.get("kernel_vfs") or {}
    policy = kernel.get("packaging")
    assert isinstance(policy, dict), (
        "pyproject.toml must declare [tool.ipfs_kit_py.kernel_vfs.packaging]"
    )
    return policy


def _requirement_name(requirement: str) -> str:
    """Return the distribution name portion of a PEP 508 requirement string."""
    return re.split(r"[<>=!~;\[]", requirement, maxsplit=1)[0].strip().lower()


def _is_exact_pin(requirement: str) -> bool:
    """True when the requirement uses an exact ``==`` version pin (no range)."""
    # Allow environment markers after ';' but the version part must be ==X.Y.Z.
    main = requirement.split(";", 1)[0].strip()
    return bool(re.fullmatch(r"[A-Za-z0-9_.-]+==[0-9]+(?:\.[0-9]+)*(?:[a-zA-Z0-9._-]*)?", main))


def windows_live_gate_admits(
    *,
    env: Mapping[str, str] | None = None,
    policy: Mapping[str, Any] | None = None,
) -> bool:
    """Evaluate the live WinFsp gate that controls the Windows OS classifier.

    Policy (fail-closed):

    * unset / empty env → not admitted;
    * truthy tokens ``1``, ``true``, ``admitted``, ``passed`` → admitted;
    * otherwise treat the value as a path to a JSON live receipt that must
      report ``status`` in {``passed``, ``admitted``} for a WinFsp/Windows
      live profile.
    """
    policy = policy if policy is not None else _packaging_policy()
    env_name = str(policy.get("windows_live_gate_env") or "IPFS_KIT_KERNEL_VFS_WINDOWS_LIVE_GATE")
    environ = env if env is not None else os.environ
    raw = str(environ.get(env_name, "") or "").strip()
    if not raw:
        return False
    if raw.lower() in {"1", "true", "yes", "admitted", "passed"}:
        return True
    path = Path(raw)
    if not path.is_file():
        return False
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(doc, dict):
        return False
    status = str(doc.get("status") or doc.get("gate_status") or "").lower()
    if status not in {"passed", "admitted"}:
        return False
    # Receipt must bind a Windows / WinFsp *live* profile (not hermetic-only).
    profile = str(doc.get("profile") or doc.get("lane") or "").lower()
    platform = str(doc.get("platform") or doc.get("os") or "").lower()
    blob = json.dumps(doc, sort_keys=True).lower()
    live_profile = any(
        token in profile
        for token in ("windows_live", "live_winfsp", "winfsp_live", "winfsp")
    )
    live_platform = platform in {"win32", "windows"} and (
        "winfsp" in blob or "live" in profile
    )
    return live_profile or live_platform


def _fresh_python(source: str, *, env: Mapping[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run *source* in a clean interpreter with package root on PYTHONPATH."""
    environment = os.environ.copy()
    if env:
        environment.update(env)
    # Prefer source tree over any site-packages copy of the package.
    environment["PYTHONPATH"] = str(PACKAGE_ROOT)
    environment["PYTHONNOUSERSITE"] = "1"
    environment.setdefault("IPFS_KIT_AUTO_INSTALL_BINARIES", "0")
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source)],
        cwd=str(PACKAGE_ROOT),
        env=environment,
        check=False,
        text=True,
        capture_output=True,
        timeout=60,
    )


# ---------------------------------------------------------------------------
# Declared packaging surface
# ---------------------------------------------------------------------------


def test_declared_outputs_exist() -> None:
    assert PYPROJECT_PATH.is_file()
    assert Path(__file__).resolve().is_file()


def test_packaging_policy_identity_and_pins() -> None:
    policy = _packaging_policy()
    assert policy["task_id"] == TASK_ID
    assert policy["schema"] == "KernelVFSPackagingPolicy@1"
    assert policy["fuse_extra"] == "fuse"
    assert policy["fuse_binding_requirement"] == "fusepy==3.0.1"
    assert policy["mount_cli_script"] == "ipfs-kit-kernel-vfs"
    assert policy["mount_cli_entry"] == "ipfs_kit_py.cli.kernel_vfs:main"
    assert policy["windows_os_classifier"] == WINDOWS_OS_CLASSIFIER
    assert policy["windows_classifier_policy"] == "live_gate_receipt"
    assert policy["windows_live_gate_env"] == "IPFS_KIT_KERNEL_VFS_WINDOWS_LIVE_GATE"
    assert policy["import_is_not_capability"] is True
    assert policy["default_wheel_inert"] is True
    assert set(policy["supported_python"]) == {"3.12", "3.13"}
    assert set(policy["supported_platforms"]) == {"linux", "windows"}


def test_core_dependencies_exclude_fuse_native_bindings() -> None:
    project = _project()
    core = [_requirement_name(dep) for dep in project["dependencies"]]
    for token in ("fusepy", "libfuse", "winfsp"):
        assert token not in core, f"core dependency must not include {token!r}"
    # Bare "fuse" as a dist name is also forbidden in core.
    assert "fuse" not in core


def test_pinned_fuse_extra_installs_binding_only() -> None:
    project = _project()
    policy = _packaging_policy()
    extras = project["optional-dependencies"]
    assert "fuse" in extras, "optional [fuse] extra must be declared"
    fuse_reqs = list(extras["fuse"])
    assert fuse_reqs, "[fuse] extra must not be empty"
    assert all(_is_exact_pin(req) for req in fuse_reqs), (
        f"[fuse] extra requirements must be exact pins, got {fuse_reqs!r}"
    )
    names = {_requirement_name(req) for req in fuse_reqs}
    assert names == {"fusepy"}
    assert fuse_reqs == [policy["fuse_binding_requirement"]]
    # Extra must not pull host drivers (libfuse packages, WinFsp installers).
    joined = " ".join(fuse_reqs).lower()
    for forbidden in ("libfuse", "winfsp", "fuse3", "libfuse2"):
        assert forbidden not in joined


def test_mount_cli_is_discoverable_in_packaging_metadata() -> None:
    project = _project()
    policy = _packaging_policy()
    scripts = project["scripts"]
    script_name = policy["mount_cli_script"]
    entry = policy["mount_cli_entry"]
    assert script_name in scripts, f"console script {script_name!r} missing"
    assert scripts[script_name] == entry
    # Entry target shape: module:attr
    module_path, _, attr = entry.partition(":")
    assert module_path and attr
    assert module_path.startswith("ipfs_kit_py.")
    assert "kernel_vfs" in module_path or "kernel_vfs" in attr or "kernel_vfs" in script_name


def test_python_version_classifiers_cover_312_and_313() -> None:
    project = _project()
    classifiers = set(project["classifiers"])
    assert project["requires-python"] == ">=3.12"
    assert "Programming Language :: Python :: 3.12" in classifiers
    assert "Programming Language :: Python :: 3.13" in classifiers
    assert "Operating System :: POSIX :: Linux" in classifiers


# ---------------------------------------------------------------------------
# Windows classifier live-gate policy
# ---------------------------------------------------------------------------


def test_windows_classifier_conditional_on_live_gate_policy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = _project()
    policy = _packaging_policy()
    env_name = str(policy["windows_live_gate_env"])
    classifiers = list(project["classifiers"])
    has_windows = WINDOWS_OS_CLASSIFIER in classifiers

    # Default environment: gate closed → classifier must be absent.
    monkeypatch.delenv(env_name, raising=False)
    assert windows_live_gate_admits(env=os.environ, policy=policy) is False
    assert has_windows is False, (
        "Windows OS classifier must stay absent until the live WinFsp gate admits it"
    )

    # Explicit admit tokens open the policy evaluation (operator override).
    for token in ("1", "true", "admitted", "passed"):
        assert windows_live_gate_admits(env={env_name: token}, policy=policy) is True

    # Receipt path: status passed + WinFsp evidence admits.
    receipt = tmp_path / "winfsp-live-receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "schema": "KernelVFSWindowsLiveReceipt@1",
                "status": "passed",
                "profile": "windows_live_winfsp",
                "platform": "win32",
            }
        ),
        encoding="utf-8",
    )
    assert windows_live_gate_admits(env={env_name: str(receipt)}, policy=policy) is True

    # Failed or hermetic-only receipts do not admit.
    failed = tmp_path / "failed.json"
    failed.write_text(json.dumps({"status": "failed", "profile": "winfsp"}), encoding="utf-8")
    assert windows_live_gate_admits(env={env_name: str(failed)}, policy=policy) is False

    hermetic = tmp_path / "hermetic.json"
    hermetic.write_text(
        json.dumps({"status": "passed", "profile": "hermetic_callbacks_only"}),
        encoding="utf-8",
    )
    assert windows_live_gate_admits(env={env_name: str(hermetic)}, policy=policy) is False

    # Packaging projection must match the currently evaluated gate.
    admitted_now = windows_live_gate_admits(env=os.environ, policy=policy)
    assert has_windows is admitted_now


# ---------------------------------------------------------------------------
# Guarded / inert imports (default wheel surface)
# ---------------------------------------------------------------------------


def test_default_import_is_inert_without_fusepy_libfuse_or_winfsp() -> None:
    """Core and kernel_vfs loader imports must not load native FUSE bindings."""
    preexisting = {name for name in FUSE_MODULE_NAMES if name in sys.modules}
    result = _fresh_python(
        """
        import sys
        import importlib

        forbidden_before = {n for n in ("fuse", "fusepy") if n in sys.modules}

        import ipfs_kit_py
        from ipfs_kit_py.kernel_vfs import platform as linux_loader
        from ipfs_kit_py.kernel_vfs import winfsp_loader as windows_loader

        # Import is not capability.
        assert linux_loader.is_binding_loaded() is False
        assert linux_loader.is_libfuse_loaded() is False
        assert windows_loader.is_binding_loaded() is False
        assert windows_loader.is_winfsp_loaded() is False

        introduced = {
            n for n in ("fuse", "fusepy") if n in sys.modules
        } - forbidden_before
        assert not introduced, f"import loaded fuse modules: {sorted(introduced)}"

        # Doctors must remain probe-only (no mount, no native load).
        linux_report = linux_loader.run_linux_doctor()
        windows_report = windows_loader.run_windows_doctor()
        assert linux_report["mounted"] is False
        assert windows_report["mounted"] is False
        assert linux_report["loader"]["binding_loaded"] is False
        assert linux_report["loader"]["libfuse_loaded"] is False
        assert windows_report["loader"]["binding_loaded"] is False
        assert windows_report["loader"]["winfsp_loaded"] is False
        assert linux_report["policy"]["no_fusepy_import"] is True
        assert windows_report["policy"]["no_fusepy_import"] is True
        print("inert-ok")
        """
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "inert-ok" in result.stdout
    # Parent process must not have gained fuse modules from the child.
    for name in FUSE_MODULE_NAMES:
        if name not in preexisting:
            assert name not in sys.modules


def test_guarded_binding_load_fails_actionably_without_fuse_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit binding load is guarded and points at the [fuse] extra."""
    from ipfs_kit_py.kernel_vfs import platform as linux_loader
    from ipfs_kit_py.kernel_vfs import winfsp_loader as windows_loader

    linux_loader.reset_loader_state()
    windows_loader.reset_loader_state()

    real_import_module = importlib.import_module

    def _missing(name: str, package: str | None = None) -> object:
        if name in FUSE_MODULE_NAMES or (
            isinstance(name, str) and name.startswith("fusepy.")
        ):
            raise ImportError(f"No module named {name!r}")
        return real_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", _missing)

    with pytest.raises(linux_loader.FuseCapabilityError) as linux_exc:
        linux_loader.load_fuse_binding(force=True)
    err = linux_exc.value
    assert err.check == "python_binding"
    assert err.support_claim == "capability_unavailable"
    assert "[fuse]" in err.remediation or "fusepy" in err.remediation.lower()

    with pytest.raises(windows_loader.FuseCapabilityError) as windows_exc:
        windows_loader.load_fuse_binding(force=True)
    win_err = windows_exc.value
    assert win_err.check == "python_binding"
    assert win_err.support_claim == "capability_unavailable"
    assert "[fuse]" in win_err.remediation or "fusepy" in win_err.remediation.lower()

    linux_loader.reset_loader_state()
    windows_loader.reset_loader_state()


# ---------------------------------------------------------------------------
# Missing driver is diagnostic
# ---------------------------------------------------------------------------


def test_missing_driver_is_diagnostic() -> None:
    """Absent native capability yields actionable doctor diagnostics, never a mount."""
    from ipfs_kit_py.kernel_vfs import platform as linux_loader
    from ipfs_kit_py.kernel_vfs import winfsp_loader as windows_loader

    linux_loader.reset_loader_state()
    windows_loader.reset_loader_state()

    # Force an empty PATH so fusermount cannot be found; still no mount.
    linux_report = linux_loader.run_linux_doctor(path_env="")
    assert linux_report["mounted"] is False
    assert linux_report["within_budget"] is True
    assert linux_report["policy"]["no_mount"] is True
    assert linux_report["policy"]["import_is_not_capability"] is True
    helper = linux_report["checks"]["fusermount_helper"]
    assert helper["available"] is False
    assert helper.get("actionable_absence")
    assert "fusermount" in str(helper["actionable_absence"]).lower()

    absence = linux_report["checks"]["actionable_absence"]
    assert absence["count"] >= 1
    assert absence["items"]
    for item in absence["items"]:
        assert item["check"]
        assert item["message"]
        assert len(item["message"]) > 10

    # Windows doctor is hermetic on non-Windows hosts: missing driver is typed.
    windows_report = windows_loader.run_windows_doctor()
    assert windows_report["mounted"] is False
    assert windows_report["within_budget"] is True
    assert windows_report["policy"]["no_mount"] is True
    win_absence = windows_report["checks"]["actionable_absence"]
    if not windows_report["native_capability_ready"]:
        assert win_absence["count"] >= 1
        assert win_absence["items"]
        for item in win_absence["items"]:
            assert item["check"]
            assert item["message"]
        assert windows_report["support_claim"] == "capability_unavailable"

    # ensure_* raises a typed diagnostic when capability is missing.
    if not linux_report["native_capability_ready"]:
        with pytest.raises(linux_loader.FuseCapabilityError) as excinfo:
            linux_loader.ensure_linux_fuse_capability(path_env="")
        err = excinfo.value
        assert err.support_claim == "capability_unavailable"
        payload = err.to_dict()
        assert payload["mounted"] is False
        assert payload.get("check") or payload.get("absences")

    linux_loader.reset_loader_state()
    windows_loader.reset_loader_state()


# ---------------------------------------------------------------------------
# Python 3.12/3.13 × Linux/Windows wheel probes
# ---------------------------------------------------------------------------


def _wheel_probe(
    *,
    python_version: str,
    platform_name: str,
    project: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Hermetic packaging probe for a target interpreter/platform tuple.

    Does not build multi-arch binaries. Validates the packaging contract that a
    default wheel for that target would advertise and load.
    """
    assert python_version in {"3.12", "3.13"}
    assert platform_name in {"linux", "windows"}

    classifiers = set(project["classifiers"])
    requires = str(project["requires-python"])
    assert requires.startswith(">="), requires
    min_version = requires.removeprefix(">=").strip()
    # 3.12 / 3.13 both satisfy >=3.12
    assert tuple(int(p) for p in python_version.split(".")) >= tuple(
        int(p) for p in min_version.split(".")
    )
    assert f"Programming Language :: Python :: {python_version}" in classifiers

    # Core wheel must not require FUSE natives for either platform.
    core_names = {_requirement_name(dep) for dep in project["dependencies"]}
    assert not core_names.intersection({"fusepy", "fuse", "libfuse", "winfsp"})

    fuse_extra = list(project["optional-dependencies"]["fuse"])
    assert fuse_extra == [policy["fuse_binding_requirement"]]
    assert all(_is_exact_pin(req) for req in fuse_extra)

    scripts = project["scripts"]
    assert scripts[policy["mount_cli_script"]] == policy["mount_cli_entry"]

    if platform_name == "linux":
        assert "Operating System :: POSIX :: Linux" in classifiers
        platform_tag = f"py{python_version.replace('.', '')}-none-any"
        os_claim = "linux"
    else:
        # Windows classifier is live-gate conditional, not automatic for the
        # pure-Python wheel. Hermetic Windows code is still shippable.
        admitted = windows_live_gate_admits(policy=policy)
        has_windows = WINDOWS_OS_CLASSIFIER in classifiers
        assert has_windows is admitted
        platform_tag = f"py{python_version.replace('.', '')}-none-any"
        os_claim = "windows_hermetic" if not admitted else "windows_live_admitted"

    return {
        "python_version": python_version,
        "platform": platform_name,
        "platform_tag": platform_tag,
        "os_claim": os_claim,
        "fuse_extra": fuse_extra,
        "mount_cli": policy["mount_cli_script"],
        "default_wheel_inert": True,
        "status": "passed",
    }


@pytest.mark.parametrize("python_version", ["3.12", "3.13"])
@pytest.mark.parametrize("platform_name", ["linux", "windows"])
def test_wheel_probes_pass_for_supported_matrix(
    python_version: str, platform_name: str
) -> None:
    project = _project()
    policy = _packaging_policy()
    report = _wheel_probe(
        python_version=python_version,
        platform_name=platform_name,
        project=project,
        policy=policy,
    )
    assert report["status"] == "passed"
    assert report["default_wheel_inert"] is True
    assert report["python_version"] == python_version
    assert report["platform"] == platform_name
    assert report["mount_cli"] == "ipfs-kit-kernel-vfs"
    assert report["fuse_extra"] == ["fusepy==3.0.1"]


def test_all_matrix_wheel_probes_join() -> None:
    """Joined receipt-style probe for the full packaging matrix."""
    project = _project()
    policy = _packaging_policy()
    reports = [
        _wheel_probe(
            python_version=py,
            platform_name=plat,
            project=project,
            policy=policy,
        )
        for py in policy["supported_python"]
        for plat in policy["supported_platforms"]
    ]
    assert len(reports) == 4
    assert all(r["status"] == "passed" for r in reports)
    assert {r["python_version"] for r in reports} == {"3.12", "3.13"}
    assert {r["platform"] for r in reports} == {"linux", "windows"}


def test_source_tree_wheel_metadata_projection_is_consistent() -> None:
    """When the package is importable, packaging extras match pyproject."""
    project = _project()
    policy = _packaging_policy()
    # Source-tree import path used by this test suite.
    import ipfs_kit_py

    assert ipfs_kit_py.__version__
    # OptionalDependencyError guidance uses the same extra name.
    err = ipfs_kit_py.OptionalDependencyError(
        "kernel VFS FUSE mount", extra="fuse", dependency="fusepy"
    )
    assert "ipfs_kit_py[fuse]" in str(err)
    assert "fusepy" in str(err)
    assert project["optional-dependencies"]["fuse"] == [
        policy["fuse_binding_requirement"]
    ]

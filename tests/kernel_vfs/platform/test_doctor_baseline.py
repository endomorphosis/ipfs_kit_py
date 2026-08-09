"""KVFS-108: bounded platform doctor and performance/resource baseline contracts.

Acceptance coverage:

* doctor finishes within five seconds;
* doctor records OS/architecture, Python binding, native ABI, device/driver/
  service, helper, mountpoint/state permissions, Docker capability, and
  actionable absence;
* doctor never mounts, installs drivers, or imports fusepy;
* baseline binds environment/workload/seed and cold/warm I/O, metadata, memory,
  handles, WAL, and ARC observations;
* workloads.json and --check-schema validate the hermetic profile.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

# tests/kernel_vfs/platform -> parents[3] == package root (ipfs_kit_py/)
PACKAGE_ROOT = Path(__file__).resolve().parents[3]
BENCHMARKS = PACKAGE_ROOT / "benchmarks" / "kernel_vfs"
BASELINE_PY = BENCHMARKS / "baseline.py"
WORKLOADS_JSON = BENCHMARKS / "workloads.json"

if str(BENCHMARKS) not in sys.path:
    sys.path.insert(0, str(BENCHMARKS))

import baseline as kvfs_baseline  # noqa: E402


REQUIRED_DOCTOR_CHECKS = (
    "os_architecture",
    "python_binding",
    "native_abi",
    "device_driver_service",
    "helper",
    "mountpoint_state_permissions",
    "docker_capability",
    "actionable_absence",
)

REQUIRED_OBSERVATIONS = (
    "sequential_io",
    "random_io",
    "metadata",
    "memory",
    "handles",
    "wal",
    "arc",
)


# ---------------------------------------------------------------------------
# Artifact presence
# ---------------------------------------------------------------------------


def test_declared_outputs_exist():
    assert BASELINE_PY.is_file(), f"missing declared output {BASELINE_PY}"
    assert WORKLOADS_JSON.is_file(), f"missing declared output {WORKLOADS_JSON}"
    # workloads.json must remain a regular file (not a symlink) so the
    # submodule can track the pinned profile without parent force-add.
    assert WORKLOADS_JSON.is_file() and not WORKLOADS_JSON.is_symlink()
    assert WORKLOADS_JSON.stat().st_size > 0


def test_workloads_schema_pins_identity_and_doctor_checks():
    doc = json.loads(WORKLOADS_JSON.read_text(encoding="utf-8"))
    assert doc["schema"] == "KernelVFSWorkloadProfile@1"
    assert doc["task_id"] == "KVFS-108"
    assert "ci-reference" in doc["resource_profiles"]
    assert set(doc["path_classes"]) >= {"cold", "warm"}
    for check in REQUIRED_DOCTOR_CHECKS:
        assert check in doc["doctor_checks"]
    for field in ("seed", "dataset", "profile", "workload", "path_class"):
        assert field in doc["identity_fields"]
    profile = doc["resource_profiles"]["ci-reference"]
    assert profile["native_mount"] is False
    assert profile["networked"] is False
    assert isinstance(profile["default_seed"], int)
    for name in profile["workloads"]:
        assert name in doc["workloads"]
    forbidden = doc["comparison_binding"]["forbidden_inferences"]
    assert "import_success_implies_native_capability" in forbidden


# ---------------------------------------------------------------------------
# Doctor
# ---------------------------------------------------------------------------


def test_doctor_finishes_within_five_seconds_and_records_required_checks():
    started = time.perf_counter()
    report = kvfs_baseline.run_doctor()
    elapsed = time.perf_counter() - started

    assert elapsed < 5.0
    assert report["elapsed_seconds"] < 5.0
    assert report["within_budget"] is True
    assert report["budget_seconds"] == 5.0
    assert report["schema"] == "KernelVFSDoctorReport@1"
    assert report["task_id"] == "KVFS-108"
    assert report["mounted"] is False
    assert report["policy"]["no_mount"] is True
    assert report["policy"]["no_fusepy_import"] is True
    assert report["policy"]["import_is_not_capability"] is True

    for name in REQUIRED_DOCTOR_CHECKS:
        assert name in report["checks"], f"missing doctor check {name}"
        entry = report["checks"][name]
        assert entry["check"] == name

    os_arch = report["checks"]["os_architecture"]
    assert os_arch["os"]
    assert os_arch["architecture"]

    binding = report["checks"]["python_binding"]
    assert binding["imported"] is False
    assert "fusepy_find_spec" in binding

    mount_state = report["checks"]["mountpoint_state_permissions"]
    assert mount_state["mounted"] is False
    assert mount_state["separated"] is True

    docker = report["checks"]["docker_capability"]
    assert docker["invoked_docker"] is False
    assert docker["privileged_profile_forbidden"] is True

    absence = report["checks"]["actionable_absence"]
    assert "items" in absence
    assert isinstance(absence["items"], list)
    # Every recorded absence must be actionable prose, not an empty marker.
    for item in absence["items"]:
        assert item["check"]
        assert isinstance(item["message"], str) and len(item["message"]) > 20


def test_doctor_absence_is_typed_not_silent_success():
    report = kvfs_baseline.run_doctor()
    # Support claim must never invent native readiness from import/docs alone.
    assert report["support_claim"] in {"capability_unavailable", "probe_passed"}
    if not report["native_capability_ready"]:
        assert report["support_claim"] == "capability_unavailable"
        assert report["checks"]["actionable_absence"]["count"] >= 1


def test_doctor_does_not_import_fusepy(monkeypatch):
    """Importing fusepy is forbidden; only find_spec may be used."""
    import importlib

    real_import_module = importlib.import_module

    def _guarded(name, *args, **kwargs):
        if name in {"fusepy", "fuse"} or name.startswith("fusepy."):
            raise AssertionError(f"doctor must not import {name}")
        return real_import_module(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", _guarded)
    # Also guard builtins.__import__ for direct import statements.
    import builtins

    real_import = builtins.__import__

    def _guarded_import(name, *args, **kwargs):
        if name in {"fusepy", "fuse"} or (
            isinstance(name, str) and name.startswith("fusepy.")
        ):
            raise AssertionError(f"doctor must not import {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _guarded_import)
    report = kvfs_baseline.run_doctor()
    assert report["checks"]["python_binding"]["imported"] is False


# ---------------------------------------------------------------------------
# Baseline
# ---------------------------------------------------------------------------


def test_baseline_binds_identity_seed_and_required_observations():
    manifest = kvfs_baseline.run_baseline("ci-reference")

    assert manifest["schema"] == "KernelVFSBaselineManifest@1"
    assert manifest["task_id"] == "KVFS-108"
    assert manifest["profile"] == "ci-reference"

    identity = manifest["identity"]
    for field in kvfs_baseline.REQUIRED_IDENTITY_FIELDS:
        assert field in identity
    assert isinstance(identity["seed"], int)
    assert identity["seed"] == 108108
    assert identity["identity_digest"]

    observations = manifest["observations"]
    for key in REQUIRED_OBSERVATIONS:
        assert key in observations

    for io_key in ("sequential_io", "random_io"):
        assert set(observations[io_key]) >= {"cold", "warm"}
        for path_class in ("cold", "warm"):
            entry = observations[io_key][path_class]
            assert entry["path_class"] == path_class
            assert "p99_ms" in entry

    for key in ("metadata", "handles", "wal", "arc"):
        assert set(observations[key]) >= {"cold", "warm"}

    assert "rss_bytes" in observations["memory"] or "working_set_bytes" in observations["memory"]
    assert observations["wal"]["warm"]["ack_state"] == "committed"
    assert 0.0 <= observations["arc"]["warm"]["hit_ratio"] <= 1.0

    assert manifest["policy"]["native_mount"] is False
    assert manifest["doctor"]["mounted"] is False


def test_check_schema_report_is_ok():
    report = kvfs_baseline.check_schema("ci-reference")
    assert report["ok"] is True
    assert report["task_id"] == "KVFS-108"
    assert report["doctor_within_budget"] is True
    assert report["doctor_mounted"] is False
    assert report["native_mount"] is False
    assert set(report["path_classes"]) == {"cold", "warm"}
    assert set(report["observation_keys"]) >= set(REQUIRED_OBSERVATIONS)
    assert set(report["doctor_checks"]) >= set(REQUIRED_DOCTOR_CHECKS)
    assert report["seed"] == 108108
    assert report["policy"]["no_fusepy_import"] is True


def test_cli_check_schema_subprocess():
    """Match the task validation command surface."""
    proc = subprocess.run(
        [sys.executable, str(BASELINE_PY), "--check-schema"],
        cwd=str(PACKAGE_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["task_id"] == "KVFS-108"

"""KVFS-501: Certify Linux ARM64 ABI and repeated mount/resource soak.

Acceptance coverage:

* native ARM64 ABI and concurrency pass;
* 100 mount/unmount and crash/recover cycles show zero leaked process /
  mount / handle / lease;
* bounded WAL / cache / memory / descriptors;
* no stale read or lost acknowledgement;
* capability absence is a finite nonpromotion receipt.

Harness implementation lives in
``ipfs_kit_py/benchmarks/kernel_vfs/linux_soak.py`` (declared output).
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[3]
SOAK_PATH = PACKAGE_ROOT / "benchmarks" / "kernel_vfs" / "linux_soak.py"
TEST_PATH = Path(__file__).resolve()


def _load_soak():
    """Load sibling benchmark soak module without requiring package init."""

    name = "kvfs501_linux_soak"
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(name, SOAK_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load soak module from {SOAK_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


soak = _load_soak()

TASK_ID = soak.TASK_ID
DEFAULT_MOUNT_CYCLES = soak.DEFAULT_MOUNT_CYCLES
DEFAULT_CRASH_CYCLES = soak.DEFAULT_CRASH_CYCLES
CAPABILITY_PROBE_BUDGET_SECONDS = soak.CAPABILITY_PROBE_BUDGET_SECONDS
READINESS_TIMEOUT_SECONDS = soak.READINESS_TIMEOUT_SECONDS
SOAK_RECEIPT_SCHEMA = soak.SOAK_RECEIPT_SCHEMA
SUPPORT_CLAIM_UNAVAILABLE = soak.SUPPORT_CLAIM_UNAVAILABLE
SUPPORT_CLAIM_LIVE_PASSED = soak.SUPPORT_CLAIM_LIVE_PASSED
SUPPORT_CLAIM_HERMETIC_ONLY = soak.SUPPORT_CLAIM_HERMETIC_ONLY
PROFILE_HERMETIC = soak.PROFILE_HERMETIC
PROFILE_LIVE = soak.PROFILE_LIVE
CycleKind = soak.CycleKind
CycleStatus = soak.CycleStatus
ExecutionPlane = soak.ExecutionPlane
SoakStatus = soak.SoakStatus
can_promote_live_support = soak.can_promote_live_support
certify_arm64_abi = soak.certify_arm64_abi
check_schema = soak.check_schema
is_native_arm64 = soak.is_native_arm64
probe_linux_capability = soak.probe_linux_capability
run_concurrency_soak = soak.run_concurrency_soak
run_crash_recover_cycle = soak.run_crash_recover_cycle
run_linux_soak = soak.run_linux_soak
run_mount_unmount_cycle = soak.run_mount_unmount_cycle
sample_resources = soak.sample_resources
assert_resource_bounds = soak.assert_resource_bounds
support_claim_for = soak.support_claim_for
architecture_label = soak.architecture_label


# ---------------------------------------------------------------------------
# Artifact / schema / bounds
# ---------------------------------------------------------------------------


def test_declared_outputs_exist() -> None:
    assert SOAK_PATH.is_file()
    assert SOAK_PATH.stat().st_size > 0
    assert TEST_PATH.is_file()
    assert TEST_PATH.stat().st_size > 0
    text = SOAK_PATH.read_text(encoding="utf-8")
    assert "KVFS-501" in text
    assert "100" in text
    assert "capability_unavailable" in text or "nonpromotion" in text


def test_task_identity_and_bounds() -> None:
    assert TASK_ID == "KVFS-501"
    assert soak.CONTRACT_VERSION == 1
    assert soak.SCHEMA_VERSION.startswith("1.")
    assert SOAK_RECEIPT_SCHEMA == "KernelVFSLinuxSoakReceipt@1"
    assert DEFAULT_MOUNT_CYCLES == 100
    assert DEFAULT_CRASH_CYCLES == 100
    assert READINESS_TIMEOUT_SECONDS == 15.0
    assert CAPABILITY_PROBE_BUDGET_SECONDS <= 5.0
    assert PROFILE_HERMETIC == "linux_hermetic_soak"
    result = check_schema()
    assert result["ok"] is True
    assert result["required"]["default_mount_cycles"] == 100


def test_soak_module_import_is_inert() -> None:
    """Importing the soak harness must not load fusepy or libfuse."""

    source = SOAK_PATH.read_text(encoding="utf-8")
    assert "import fuse\n" not in source
    assert "import fusepy\n" not in source
    assert "from fuse " not in source
    assert "from fusepy " not in source
    assert "ctypes.CDLL" not in source
    pre_existing = {name for name in ("fuse", "fusepy") if name in sys.modules}
    _ = probe_linux_capability(budget_seconds=1.0)
    for name in ("fuse", "fusepy"):
        if name not in pre_existing:
            assert name not in sys.modules


# ---------------------------------------------------------------------------
# Native ARM64 ABI certification
# ---------------------------------------------------------------------------


def test_arm64_abi_certification_is_finite() -> None:
    receipt = certify_arm64_abi()
    record = receipt.to_record()
    assert record["task_id"] == "KVFS-501"
    assert record["schema"].endswith("@1")
    assert record["support_promoted"] is False
    assert record["abi_ok"] is True
    assert record["pointer_bits"] in {32, 64}
    assert record["byteorder"] in {"little", "big"}
    assert record["architecture"]
    # Alias normalization is always validated inside the receipt.
    assert record["detail"]["checks"]["normalize_arm64_alias"] is True
    assert record["detail"]["checks"]["normalize_aarch64"] is True

    if is_native_arm64():
        assert receipt.is_arm64 is True
        assert receipt.architecture == "aarch64"
        assert receipt.pointer_bits == 64
        assert receipt.byteorder == "little"
        assert "ARM64" in receipt.message or "arm64" in receipt.message.lower()
        assert receipt.detail["checks"]["arm64_is_64bit"] is True
        assert receipt.detail["checks"]["arm64_little_endian"] is True
    else:
        # Non-ARM64 hosts still get a finite labeled ABI receipt without
        # claiming native ARM64 soak promotion.
        assert receipt.support_promoted is False
        assert "not claimed" in receipt.message or receipt.architecture != "aarch64"


def test_architecture_label_normalizes_arm64_alias() -> None:
    from ipfs_kit_py.kernel_vfs.platform import normalize_machine

    assert normalize_machine("arm64") == "aarch64"
    assert normalize_machine("aarch64") == "aarch64"
    label = architecture_label()
    assert isinstance(label, str) and label


# ---------------------------------------------------------------------------
# Capability probe — finite nonpromotion receipt
# ---------------------------------------------------------------------------


def test_capability_probe_is_bounded_finite_nonpromotion(tmp_path: Path) -> None:
    started = time.monotonic()
    receipt = probe_linux_capability(
        budget_seconds=CAPABILITY_PROBE_BUDGET_SECONDS,
        mountpoint=tmp_path / "mnt",
        state_dir=tmp_path / "state",
    )
    elapsed = time.monotonic() - started
    assert elapsed < 5.5
    assert receipt.within_budget is True
    assert receipt.budget_seconds <= 5.0
    assert receipt.elapsed_seconds < 5.5
    assert receipt.finite is True
    assert receipt.support_promoted is False
    record = receipt.to_record()
    assert record["task_id"] == "KVFS-501"
    assert record["support_promoted"] is False
    assert record["finite"] is True
    assert record["nonpromotion"] is True
    assert record["schema"].endswith("@1")


def test_absent_capability_is_finite_nonpromotion_receipt(tmp_path: Path) -> None:
    """Capability absence must never promote live support."""

    receipt = probe_linux_capability(
        budget_seconds=CAPABILITY_PROBE_BUDGET_SECONDS,
        mountpoint=tmp_path / "mnt",
        state_dir=tmp_path / "state",
    )
    if not receipt.native_ready:
        assert receipt.support_claim == SUPPORT_CLAIM_UNAVAILABLE
        assert receipt.support_promoted is False
        assert receipt.finite is True
        assert "nonpromotion" in receipt.message.lower() or "unavailable" in (
            receipt.message.lower()
        )
        assert (
            can_promote_live_support(
                native_ready=False,
                support_claim=SUPPORT_CLAIM_LIVE_PASSED,
                status="passed",
                profile=PROFILE_LIVE,
            )
            is False
        )
        assert (
            can_promote_live_support(
                native_ready=receipt.native_ready,
                support_claim=receipt.support_claim,
                status="passed",
                profile=PROFILE_LIVE,
            )
            is False
        )


def test_support_claim_helper_fail_closed() -> None:
    assert (
        support_claim_for(
            native_ready=False,
            soak_passed=True,
            plane=ExecutionPlane.LIVE,
        )
        == SUPPORT_CLAIM_UNAVAILABLE
    )
    assert (
        support_claim_for(
            native_ready=True,
            soak_passed=True,
            plane=ExecutionPlane.LIVE,
        )
        == SUPPORT_CLAIM_LIVE_PASSED
    )
    assert (
        support_claim_for(
            native_ready=True,
            soak_passed=True,
            plane=ExecutionPlane.HERMETIC,
        )
        == SUPPORT_CLAIM_HERMETIC_ONLY
    )
    assert (
        can_promote_live_support(
            native_ready=True,
            support_claim=SUPPORT_CLAIM_LIVE_PASSED,
            status="passed",
            profile=PROFILE_LIVE,
        )
        is True
    )
    assert (
        can_promote_live_support(
            native_ready=True,
            support_claim=SUPPORT_CLAIM_LIVE_PASSED,
            status="passed",
            profile=PROFILE_HERMETIC,
        )
        is False
    )


# ---------------------------------------------------------------------------
# Concurrency soak
# ---------------------------------------------------------------------------


def test_concurrency_soak_passes_and_is_bounded() -> None:
    receipt = run_concurrency_soak(workers=4, duration_seconds=0.35, seed=501)
    assert receipt.success is True, receipt.to_record()
    assert receipt.deadlock_free is True
    assert receipt.bounded is True
    assert receipt.errors == 0
    assert receipt.active_callbacks_final == 0
    assert receipt.waiters_final == 0
    assert receipt.open_handles_final == 0
    assert receipt.ops_ok + receipt.ops_conflict > 0
    record = receipt.to_record()
    assert record["task_id"] == "KVFS-501"
    assert record["schema"].endswith("@1")


# ---------------------------------------------------------------------------
# Single cycle smoke (mount/unmount and crash/recover)
# ---------------------------------------------------------------------------


def test_single_mount_unmount_cycle_is_clean(tmp_path: Path) -> None:
    receipt = run_mount_unmount_cycle(tmp_path, cycle_index=0)
    assert receipt.success is True, receipt.to_record()
    assert receipt.status is CycleStatus.PASSED
    assert receipt.kind is CycleKind.MOUNT_UNMOUNT
    assert receipt.mount_released is True
    assert receipt.lease_released is True
    assert receipt.handles_released is True
    assert receipt.process_reaped is True
    assert receipt.stale_read is False
    assert receipt.lost_ack is False
    assert receipt.elapsed_seconds < READINESS_TIMEOUT_SECONDS + 10.0


def test_single_crash_recover_cycle_is_clean(tmp_path: Path) -> None:
    receipt = run_crash_recover_cycle(tmp_path, cycle_index=0)
    assert receipt.success is True, receipt.to_record()
    assert receipt.status is CycleStatus.PASSED
    assert receipt.kind is CycleKind.CRASH_RECOVER
    assert receipt.mount_released is True
    assert receipt.lease_released is True
    assert receipt.handles_released is True
    assert receipt.process_reaped is True
    assert receipt.recovery_preserved is True
    assert receipt.stale_read is False
    assert receipt.lost_ack is False
    assert receipt.detail.get("arc_stale_rejected") is True


# ---------------------------------------------------------------------------
# Resource bounds helper
# ---------------------------------------------------------------------------


def test_resource_bounds_helper_accepts_stable_snapshots() -> None:
    baseline = sample_resources()
    current = sample_resources()
    detail = assert_resource_bounds(baseline, current)
    assert detail["bounded"] is True
    assert detail["rss_growth_bytes"] >= 0
    assert detail["fd_growth"] >= 0


# ---------------------------------------------------------------------------
# Full 100-cycle soak (acceptance)
# ---------------------------------------------------------------------------


def test_full_arm64_mount_resource_soak_100_cycles(tmp_path: Path) -> None:
    """Acceptance: 100 mount/unmount + 100 crash/recover, zero leaks/bounds."""

    work = tmp_path / "soak-full"
    started = time.monotonic()
    suite = run_linux_soak(
        work,
        mount_cycles=DEFAULT_MOUNT_CYCLES,
        crash_cycles=DEFAULT_CRASH_CYCLES,
        concurrency_seconds=0.4,
        concurrency_workers=4,
    )
    elapsed = time.monotonic() - started
    record = suite.to_record()

    # Identity / schema
    assert record["schema"] == SOAK_RECEIPT_SCHEMA
    assert record["task_id"] == "KVFS-501"
    assert record["required_mount_cycles"] == 100
    assert record["required_crash_cycles"] == 100
    assert record["readiness_timeout_seconds"] == 15.0

    # ABI + concurrency
    assert suite.abi.abi_ok is True, suite.abi.to_record()
    assert suite.concurrency.success is True, suite.concurrency.to_record()
    assert suite.concurrency.deadlock_free is True
    assert suite.concurrency.bounded is True

    # 100 + 100 cycles completed successfully
    assert suite.mount_cycle_count == 100, record
    assert suite.crash_cycle_count == 100, record
    assert all(c.success for c in suite.mount_cycles), [
        c.to_record() for c in suite.mount_cycles if not c.success
    ][:3]
    assert all(c.success for c in suite.crash_cycles), [
        c.to_record() for c in suite.crash_cycles if not c.success
    ][:3]

    # Zero leaks
    assert suite.leaked_processes == 0
    assert suite.leaked_mounts == 0
    assert suite.leaked_handles == 0
    assert suite.leaked_leases == 0
    assert record["zero_leaks"] is True

    # No stale read / lost acknowledgement
    assert suite.stale_reads == 0
    assert suite.lost_acknowledgements == 0
    assert record["zero_stale_or_lost"] is True

    # Resource bounds
    assert suite.detail.get("resource_ok") is True, suite.resource_bounds
    assert suite.resource_bounds.get("bounded") is True
    assert suite.resource_final.open_handles == 0
    assert len(suite.resource_final.child_pids) == 0

    # Capability absence is finite nonpromotion
    cap = suite.capability
    assert cap.finite is True
    assert cap.support_promoted is False
    if not suite.native_ready:
        assert suite.support_claim == SUPPORT_CLAIM_UNAVAILABLE
        assert suite.support_promoted is False
        assert suite.status == SUPPORT_CLAIM_UNAVAILABLE
        assert record["support_promoted"] is False
        assert record["live"] is False
        assert record["fuse"] is False
        assert suite.profile == PROFILE_HERMETIC
        # Finite receipt (probe terminated within budget)
        assert cap.within_budget is True
        assert "nonpromotion" in cap.message.lower() or cap.support_claim == (
            SUPPORT_CLAIM_UNAVAILABLE
        )
    else:
        # Capable host: still never promote without explicit live plane pass.
        if suite.plane is ExecutionPlane.HERMETIC:
            assert suite.support_promoted is False
            assert suite.profile == PROFILE_HERMETIC

    # Durable receipts written
    receipts = work / "receipts"
    assert (receipts / "suite.json").is_file()
    assert (receipts / "capability.json").is_file()
    assert (receipts / "abi.json").is_file()
    assert (receipts / "concurrency.json").is_file()
    suite_payload = json.loads((receipts / "suite.json").read_text(encoding="utf-8"))
    assert suite_payload["task_id"] == "KVFS-501"
    assert suite_payload["zero_leaks"] is True
    assert suite_payload["mount_cycle_count"] == 100
    assert suite_payload["crash_cycle_count"] == 100

    # Wall-clock sanity: full soak must finish in a bounded CI window.
    assert elapsed < 3600.0
    assert suite.elapsed_seconds < 3600.0


def test_short_soak_receipt_shape_matches_acceptance(tmp_path: Path) -> None:
    """Smaller cycle count still emits the full receipt shape (diagnostics)."""

    suite = run_linux_soak(
        tmp_path / "short",
        mount_cycles=3,
        crash_cycles=3,
        concurrency_seconds=0.2,
        concurrency_workers=3,
    )
    record = suite.to_record()
    for key in (
        "schema",
        "task_id",
        "status",
        "profile",
        "architecture",
        "support_claim",
        "support_promoted",
        "native_ready",
        "abi",
        "capability",
        "concurrency",
        "mount_cycle_count",
        "crash_cycle_count",
        "leaked_processes",
        "leaked_mounts",
        "leaked_handles",
        "leaked_leases",
        "stale_reads",
        "lost_acknowledgements",
        "zero_leaks",
        "zero_stale_or_lost",
        "resource_baseline",
        "resource_final",
        "resource_bounds",
    ):
        assert key in record, key
    assert suite.mount_cycle_count == 3
    assert suite.crash_cycle_count == 3
    assert all(c.success for c in suite.mount_cycles)
    assert all(c.success for c in suite.crash_cycles)
    assert suite.abi.abi_ok is True
    assert suite.concurrency.success is True
    if not suite.native_ready:
        assert suite.support_promoted is False
        assert suite.support_claim == SUPPORT_CLAIM_UNAVAILABLE


def test_suite_never_promotes_without_native_capability(tmp_path: Path) -> None:
    suite = run_linux_soak(
        tmp_path / "nopromo",
        mount_cycles=2,
        crash_cycles=2,
        concurrency_seconds=0.15,
    )
    if not suite.native_ready:
        assert suite.support_promoted is False
        assert suite.capability.support_promoted is False
        assert suite.capability.finite is True
        assert suite.support_claim == SUPPORT_CLAIM_UNAVAILABLE
        assert can_promote_live_support(
            native_ready=suite.native_ready,
            support_claim=suite.support_claim,
            status="passed",
            profile=PROFILE_LIVE,
        ) is False

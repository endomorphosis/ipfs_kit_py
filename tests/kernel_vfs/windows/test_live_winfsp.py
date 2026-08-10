"""KVFS-603: Real WinFsp conformance with PowerShell/Explorer-compatible ops.

Acceptance coverage:

* pinned WinFsp x64 live receipts cover PowerShell and Explorer-compatible
  CRUD, random I/O, metadata, Unicode/case, concurrent open/delete/rename,
  fsync, forced crash/recovery, ARC coherence, drive/directory cleanup;
* each case is bounded (15 s readiness, 60 s per case, cleanup finally +
  watchdog);
* absent capability emits ``capability_unavailable`` and **cannot** promote
  live Windows support.

On non-capable runners (default CI / Linux validation) the hermetic plane
executes the full case matrix through :class:`WindowsMountLifecycle` and the
WinFsp FUSE-compat adapter. Suite receipts use the hermetic profile so the
packaging live gate never admits support from hermetic-only evidence.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

import pytest

from ipfs_kit_py.kernel_vfs.windows import (
    DEFAULT_READINESS_TIMEOUT_SECONDS,
    WindowsMountMode,
)
from ipfs_kit_py.kernel_vfs.windows_semantics import MountRootKind

PACKAGE_ROOT = Path(__file__).resolve().parents[3]
HARNESS_PATH = Path(__file__).resolve().parent / "live_harness.py"
TEST_PATH = Path(__file__).resolve()


def _load_live_harness():
    """Load sibling live_harness.py without requiring a package __init__."""

    name = "kvfs603_windows_live_harness"
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(name, HARNESS_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load live harness from {HARNESS_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


harness = _load_live_harness()

CAPABILITY_PROBE_BUDGET_SECONDS = harness.CAPABILITY_PROBE_BUDGET_SECONDS
CASE_TIMEOUT_SECONDS = harness.CASE_TIMEOUT_SECONDS
LIVE_RECEIPT_SCHEMA = harness.LIVE_RECEIPT_SCHEMA
PINNED_ARCHITECTURE = harness.PINNED_ARCHITECTURE
PINNED_DLL = harness.PINNED_DLL
PROFILE_HERMETIC = harness.PROFILE_HERMETIC
PROFILE_LIVE = harness.PROFILE_LIVE
READINESS_TIMEOUT_SECONDS = harness.READINESS_TIMEOUT_SECONDS
REQUIRED_CASE_IDS = harness.REQUIRED_CASE_IDS
SUPPORT_CLAIM_HERMETIC_ONLY = harness.SUPPORT_CLAIM_HERMETIC_ONLY
SUPPORT_CLAIM_LIVE_PASSED = harness.SUPPORT_CLAIM_LIVE_PASSED
SUPPORT_CLAIM_UNAVAILABLE = harness.SUPPORT_CLAIM_UNAVAILABLE
TASK_ID = harness.TASK_ID
CaseStatus = harness.CaseStatus
CaseWatchdog = harness.CaseWatchdog
ConformanceCaseId = harness.ConformanceCaseId
ExecutionPlane = harness.ExecutionPlane
SupportPromotionError = harness.SupportPromotionError
WinFspLiveHarness = harness.WinFspLiveHarness
can_promote_live_support = harness.can_promote_live_support
case_timeout_seconds = harness.case_timeout_seconds
probe_winfsp_capability = harness.probe_winfsp_capability
readiness_timeout_seconds = harness.readiness_timeout_seconds
required_case_ids = harness.required_case_ids
run_live_conformance = harness.run_live_conformance
support_claim_for = harness.support_claim_for


# ---------------------------------------------------------------------------
# Artifact / schema / bounds
# ---------------------------------------------------------------------------


def test_declared_outputs_exist() -> None:
    assert HARNESS_PATH.is_file()
    assert HARNESS_PATH.stat().st_size > 0
    assert TEST_PATH.is_file()
    assert TEST_PATH.stat().st_size > 0


def test_task_identity_and_bounds() -> None:
    assert TASK_ID == "KVFS-603"
    assert harness.CONTRACT_VERSION == 1
    assert harness.SCHEMA_VERSION.startswith("1.")
    assert LIVE_RECEIPT_SCHEMA == "KernelVFSWindowsLiveReceipt@1"
    assert READINESS_TIMEOUT_SECONDS == 15.0
    assert DEFAULT_READINESS_TIMEOUT_SECONDS == 15.0
    assert CASE_TIMEOUT_SECONDS == 60.0
    assert CAPABILITY_PROBE_BUDGET_SECONDS <= 5.0
    assert readiness_timeout_seconds() == 15.0
    assert case_timeout_seconds() == 60.0
    assert PINNED_ARCHITECTURE == "x64"
    assert PINNED_DLL == "winfsp-x64.dll"
    assert PROFILE_LIVE == "windows_live_winfsp"
    assert "KVFS-603" in HARNESS_PATH.read_text(encoding="utf-8")
    assert "capability_unavailable" in HARNESS_PATH.read_text(encoding="utf-8")


def test_required_case_matrix_is_complete() -> None:
    ids = required_case_ids()
    expected = {
        "powershell_crud",
        "explorer_crud",
        "random_io",
        "metadata",
        "unicode_case",
        "concurrent_open_delete_rename",
        "fsync",
        "forced_crash_recovery",
        "arc_coherence",
        "drive_cleanup",
        "directory_cleanup",
    }
    assert set(ids) == expected
    assert tuple(c.value for c in REQUIRED_CASE_IDS) == ids
    # Every case has a runner.
    for case_id in ConformanceCaseId:
        assert case_id in harness.CASE_RUNNERS


def test_harness_module_import_is_inert() -> None:
    """Importing the live harness must not load fusepy or WinFsp DLLs."""

    source = HARNESS_PATH.read_text(encoding="utf-8")
    # No hard top-level fusepy import; doctor is used without native DLL load.
    assert "import fuse\n" not in source
    assert "import fusepy\n" not in source
    assert "from fuse " not in source
    assert "from fusepy " not in source
    assert "LoadLibrary" not in source
    assert "ctypes.CDLL" not in source
    assert "ctypes.WinDLL" not in source
    # Harness load must not force a native fuse module into sys.modules.
    pre_existing = {name for name in ("fuse", "fusepy") if name in sys.modules}
    _ = harness.probe_winfsp_capability(budget_seconds=1.0)
    for name in ("fuse", "fusepy"):
        if name not in pre_existing:
            assert name not in sys.modules


# ---------------------------------------------------------------------------
# Capability probe — fail-closed, bounded, no support promotion
# ---------------------------------------------------------------------------


def test_capability_probe_is_bounded_and_typed(tmp_path: Path) -> None:
    started = time.monotonic()
    receipt = probe_winfsp_capability(
        budget_seconds=CAPABILITY_PROBE_BUDGET_SECONDS,
        state_dir=tmp_path / "cap-state",
    )
    elapsed = time.monotonic() - started
    assert elapsed < 5.5
    assert receipt.within_budget is True
    assert receipt.budget_seconds <= 5.0
    assert receipt.elapsed_seconds < 5.5
    assert receipt.pinned_architecture == "x64"
    assert receipt.pinned_dll == "winfsp-x64.dll"
    assert receipt.support_promoted is False
    record = receipt.to_record()
    assert record["task_id"] == "KVFS-603"
    assert record["support_promoted"] is False
    assert record["schema"].endswith("@1")


def test_absent_capability_cannot_promote_support(tmp_path: Path) -> None:
    """On this validation host, live support must not be promoted."""

    with WinFspLiveHarness(tmp_path / "work-cap") as h:
        cap = h.probe()
        # Linux validation environment (and any non-WinFsp host) is unavailable.
        if not cap.is_windows or not cap.native_ready:
            assert cap.support_claim == SUPPORT_CLAIM_UNAVAILABLE
            assert cap.native_ready is False
            assert can_promote_live_support(
                native_ready=cap.native_ready,
                support_claim=cap.support_claim,
                status="passed",
                profile=PROFILE_LIVE,
                architecture=cap.architecture,
            ) is False
            # Even a forged live-looking claim is rejected without native_ready.
            assert can_promote_live_support(
                native_ready=False,
                support_claim=SUPPORT_CLAIM_LIVE_PASSED,
                status="passed",
                profile=PROFILE_LIVE,
                architecture=PINNED_ARCHITECTURE,
            ) is False
            assert h.plane is ExecutionPlane.HERMETIC


def test_support_claim_helper_fail_closed() -> None:
    assert (
        support_claim_for(
            native_ready=False,
            live_cases_passed=True,
            plane=ExecutionPlane.LIVE,
        )
        == SUPPORT_CLAIM_UNAVAILABLE
    )
    assert (
        support_claim_for(
            native_ready=True,
            live_cases_passed=True,
            plane=ExecutionPlane.LIVE,
        )
        == SUPPORT_CLAIM_LIVE_PASSED
    )
    assert (
        support_claim_for(
            native_ready=True,
            live_cases_passed=True,
            plane=ExecutionPlane.HERMETIC,
        )
        == SUPPORT_CLAIM_HERMETIC_ONLY
    )
    assert can_promote_live_support(
        native_ready=True,
        support_claim=SUPPORT_CLAIM_LIVE_PASSED,
        status="passed",
        profile=PROFILE_LIVE,
        architecture="x64",
    ) is True
    assert can_promote_live_support(
        native_ready=True,
        support_claim=SUPPORT_CLAIM_LIVE_PASSED,
        status="passed",
        profile=PROFILE_HERMETIC,
        architecture="x64",
    ) is False


# ---------------------------------------------------------------------------
# Watchdog bounds
# ---------------------------------------------------------------------------


def test_case_watchdog_fires_after_timeout() -> None:
    wd = CaseWatchdog(timeout_seconds=0.15)
    wd.start("watchdog-demo")
    time.sleep(0.35)
    assert wd.fired is True
    wd.cancel()


def test_case_watchdog_cancel_before_fire() -> None:
    wd = CaseWatchdog(timeout_seconds=2.0)
    wd.start("watchdog-cancel")
    time.sleep(0.05)
    wd.cancel()
    assert wd.fired is False


# ---------------------------------------------------------------------------
# Mount session readiness bound
# ---------------------------------------------------------------------------


def test_hermetic_session_ready_within_15_seconds(tmp_path: Path) -> None:
    with WinFspLiveHarness(tmp_path / "work-ready") as h:
        started = time.monotonic()
        session = h.open_session(kind=MountRootKind.DRIVE_LETTER, root="Z:")
        elapsed = time.monotonic() - started
        try:
            assert elapsed < READINESS_TIMEOUT_SECONDS
            assert session.lifecycle.ready is True
            assert session.lifecycle.recovery_complete is True
            assert session.lifecycle.mode is WindowsMountMode.HERMETIC
            assert session.adapter is not None
            assert session.operations is not None
            status = session.lifecycle.status()
            assert status.ready is True
            resources = status.to_record()["resources"]
            assert resources["drive_letter"] == "Z:"
            assert resources["pid"] > 0
            assert resources["wal_directory"]
            assert resources["cache_directory"]
        finally:
            session.close()


def test_exclusive_drive_lease_between_harness_sessions(tmp_path: Path) -> None:
    work = tmp_path / "work-lease"
    with WinFspLiveHarness(work, drive_letter="Y:") as h:
        first = h.open_session(kind=MountRootKind.DRIVE_LETTER, root="Y:")
        try:
            # Second lifecycle sharing the same lease root must fail closed.
            from ipfs_kit_py.kernel_vfs.windows import (
                WindowsMountLifecycle,
                WindowsResourceLeaseError,
            )

            second = WindowsMountLifecycle(
                work / "state-b",
                mount_id="mount:lease-b",
                mode=WindowsMountMode.HERMETIC,
                lease_root=h.lease_root,
            )
            try:
                with pytest.raises(WindowsResourceLeaseError):
                    second.mount("Y:", kind=MountRootKind.DRIVE_LETTER)
            finally:
                second.close()
        finally:
            first.close()


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
    with WinFspLiveHarness(tmp_path / f"work-{case_id.value}") as h:
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
        # Absent capability never promotes.
        cap = h.probe()
        if not cap.native_ready:
            assert receipt.support_promoted is False
            assert receipt.support_claim == SUPPORT_CLAIM_UNAVAILABLE
            assert receipt.plane is ExecutionPlane.HERMETIC
        # Durable case receipt written.
        path = h.receipts_directory / f"case-{case_id.value}.json"
        assert path.is_file()
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["case_id"] == case_id.value
        assert payload["success"] is True


def test_powershell_crud_receipt_names_client(tmp_path: Path) -> None:
    with WinFspLiveHarness(tmp_path / "work-ps") as h:
        receipt = h.run_case(ConformanceCaseId.POWERSHELL_CRUD)
        assert receipt.success is True
        assert receipt.detail.get("client") == "powershell"
        assert "New-Item" in receipt.detail.get("operations", [])


def test_explorer_crud_receipt_names_client(tmp_path: Path) -> None:
    with WinFspLiveHarness(tmp_path / "work-exp") as h:
        receipt = h.run_case(ConformanceCaseId.EXPLORER_CRUD)
        assert receipt.success is True
        assert receipt.detail.get("client") == "explorer"
        assert "NewFolder" in receipt.detail.get("operations", [])


def test_forced_crash_recovery_preserves_wal_and_order(tmp_path: Path) -> None:
    with WinFspLiveHarness(tmp_path / "work-crash") as h:
        receipt = h.run_case(ConformanceCaseId.FORCED_CRASH_RECOVERY)
        assert receipt.success is True
        assert receipt.detail.get("crashed") is True
        assert receipt.detail.get("wal_preserved") is True
        assert receipt.detail.get("recovered") is True
        assert receipt.detail.get("recovery_before_ready") is True


def test_arc_coherence_rejects_stale_generation(tmp_path: Path) -> None:
    with WinFspLiveHarness(tmp_path / "work-arc") as h:
        receipt = h.run_case(ConformanceCaseId.ARC_COHERENCE)
        assert receipt.success is True
        assert receipt.detail.get("stale_rejected") is True
        assert receipt.detail.get("generation") == "g:2"
        assert receipt.detail.get("published") is True


def test_drive_and_directory_cleanup_release_leases(tmp_path: Path) -> None:
    with WinFspLiveHarness(tmp_path / "work-clean") as h:
        drive = h.run_case(ConformanceCaseId.DRIVE_CLEANUP)
        assert drive.success is True
        assert drive.detail.get("leases_released") is True
        assert drive.detail.get("process_released") is True
        assert drive.detail.get("wal_preserved") is True

        directory = h.run_case(ConformanceCaseId.DIRECTORY_CLEANUP)
        assert directory.success is True
        assert directory.detail.get("leases_released") is True
        assert directory.detail.get("process_released") is True
        assert directory.detail.get("idempotent_unmount") is True
        assert directory.detail.get("root_kind") == MountRootKind.DIRECTORY.value


# ---------------------------------------------------------------------------
# Full suite receipt — packaging live-gate compatible shape
# ---------------------------------------------------------------------------


def test_full_suite_receipt_fail_closed_without_live_capability(
    tmp_path: Path,
) -> None:
    suite = run_live_conformance(tmp_path / "work-suite")
    record = suite.to_record()

    assert record["schema"] == LIVE_RECEIPT_SCHEMA
    assert record["task_id"] == "KVFS-603"
    assert record["readiness_timeout_seconds"] == 15.0
    assert record["case_timeout_seconds"] == 60.0
    assert set(record["required_case_ids"]) == set(required_case_ids())
    assert len(record["cases"]) == len(REQUIRED_CASE_IDS)
    assert all(case["success"] for case in record["cases"])

    # Without native WinFsp, support must not be promoted and profile must not
    # admit the packaging live gate as a windows live receipt.
    if not suite.native_ready:
        assert suite.support_promoted is False
        assert suite.support_claim == SUPPORT_CLAIM_UNAVAILABLE
        assert suite.profile == PROFILE_HERMETIC
        assert suite.status == SUPPORT_CLAIM_UNAVAILABLE
        assert record["support_promoted"] is False
        assert record["live"] is False
        assert record["status"] not in {"passed", "admitted"}
        # Packaging helper requires profile tokens like windows_live / winfsp
        # *and* passed status. Hermetic profile alone must not admit.
        profile = str(record.get("profile") or "").lower()
        assert "windows_live" not in profile
        assert profile == PROFILE_HERMETIC
        assert record.get("detail", {}).get("matrix_passed") is True

    # Capability sub-receipt is present and bounded.
    cap = record["capability"]
    assert cap["support_promoted"] is False
    assert cap["budget_seconds"] <= 5.0
    assert cap["within_budget"] is True


def test_suite_writes_durable_receipts(tmp_path: Path) -> None:
    work = tmp_path / "work-durable"
    with WinFspLiveHarness(work) as h:
        suite = h.run_suite()
        assert suite.status in {
            "passed",
            "failed",
            "hermetic_passed",
            SUPPORT_CLAIM_UNAVAILABLE,
        }
        assert (h.receipts_directory / "suite.json").is_file()
        assert (h.receipts_directory / "capability.json").is_file()
        for case_id in REQUIRED_CASE_IDS:
            assert (h.receipts_directory / f"case-{case_id.value}.json").is_file()
        # Re-read suite and confirm support promotion invariant.
        payload = json.loads(
            (h.receipts_directory / "suite.json").read_text(encoding="utf-8")
        )
        if not payload.get("native_ready"):
            assert payload["support_promoted"] is False
            assert payload["support_claim"] == SUPPORT_CLAIM_UNAVAILABLE
            # Packaging live-gate requires status in {passed, admitted}.
            assert payload["status"] not in {"passed", "admitted"}


def test_harness_cleanup_is_idempotent(tmp_path: Path) -> None:
    with WinFspLiveHarness(tmp_path / "work-idem") as h:
        session = h.open_session(root="W:")
        session.close()
        h.cleanup()
        h.cleanup()  # second call must not raise
        h.close()
        h.close()


def test_prefer_live_without_capability_stays_hermetic(tmp_path: Path) -> None:
    with WinFspLiveHarness(tmp_path / "work-pref", prefer_live=True) as h:
        cap = h.probe()
        if not cap.native_ready:
            assert h.plane is ExecutionPlane.HERMETIC
            receipt = h.run_case(ConformanceCaseId.METADATA)
            assert receipt.plane is ExecutionPlane.HERMETIC
            assert receipt.support_promoted is False


def test_support_promotion_error_type_is_exported() -> None:
    err = SupportPromotionError()
    assert err.code == "SUPPORT_PROMOTION_BLOCKED"
    assert "promote" in err.message.lower()


def test_harness_to_record_lists_required_cases(tmp_path: Path) -> None:
    with WinFspLiveHarness(tmp_path / "work-rec") as h:
        h.probe()
        record = h.to_record()
        assert record["task_id"] == "KVFS-603"
        assert set(record["required_case_ids"]) == set(required_case_ids())
        assert record["readiness_timeout_seconds"] == 15.0
        assert record["case_timeout_seconds"] == 60.0

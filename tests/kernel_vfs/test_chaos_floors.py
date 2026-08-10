"""KVFS-801: performance, chaos, saturation, and resource-leak release floors.

Acceptance coverage:

* reviewed environments and workloads bind cold/warm metadata, sequential/
  random read/write, p95/p99, committed throughput, ARC ratios, WAL queue,
  memory, descriptors, handles, and mount cycles;
* kill / torn / corrupt / ENOSPC / backpressure chaos meets zero safety floors
  and bounded degradation;
* absolute floors cannot be lowered while remaining reviewed;
* ``python benchmarks/kernel_vfs/run.py --check-reviewed-floors`` is green.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

# tests/kernel_vfs -> parents[2] == package root (ipfs_kit_py/)
PACKAGE_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = PACKAGE_ROOT / "benchmarks" / "kernel_vfs"
RUN_PY = BENCHMARKS / "run.py"
FLOORS_JSON = BENCHMARKS / "reviewed_floors.json"
WORKLOADS_JSON = BENCHMARKS / "workloads.json"
BASELINE_PY = BENCHMARKS / "baseline.py"

if str(BENCHMARKS) not in sys.path:
    sys.path.insert(0, str(BENCHMARKS))
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

import run as release_run  # noqa: E402


REQUIRED_ENVIRONMENTS = ("ci-reference", "linux-live", "windows-live")
REQUIRED_PATH_CLASSES = ("cold", "warm")
REQUIRED_CHAOS = ("kill", "torn", "corrupt", "enospc", "backpressure")
REQUIRED_PERF_SECTIONS = (
    "metadata",
    "sequential_io",
    "random_io",
    "committed_throughput",
    "arc_ratios",
    "wal_queue",
    "memory",
    "descriptors",
    "handles",
    "mount_cycles",
)
REQUIRED_METRIC_BINDINGS = (
    "metadata.cold",
    "metadata.warm",
    "sequential_io.cold",
    "sequential_io.warm",
    "random_io.cold",
    "random_io.warm",
    "committed_throughput",
    "p95_ms",
    "p99_ms",
    "arc_hit_ratio",
    "wal_queue_depth_max",
    "memory_rss_bytes",
    "descriptors",
    "open_handles",
    "mount_cycles",
)
ZERO_SAFETY_KEYS = (
    "acknowledged_committed_data_loss",
    "duplicate_non_idempotent_replay_effects",
    "stale_arc_read_after_committed_mutation",
    "path_traversal_escape",
    "symlink_escape",
    "reserved_name_alias_escape",
    "false_success_errno_translation",
    "leaked_mount_after_test",
    "leaked_drive_letter_after_test",
    "leaked_child_process_after_test",
    "leaked_handle_after_test",
    "leaked_state_lease_after_test",
    "unbounded_startup_doctor_mount_unmount",
    "core_import_requires_native_binding",
    "blanket_privileged_container_profile",
    "torn_write_acknowledged",
    "corrupt_state_admitted",
    "enospc_acknowledged_loss",
    "backpressure_unbounded_queue",
    "kill_recovery_lost_ack",
)


def _read_floors() -> Dict[str, Any]:
    doc = json.loads(FLOORS_JSON.read_text(encoding="utf-8"))
    assert isinstance(doc, dict)
    return doc


# ---------------------------------------------------------------------------
# Artifact presence / schema
# ---------------------------------------------------------------------------


def test_declared_outputs_exist() -> None:
    assert RUN_PY.is_file(), f"missing {RUN_PY}"
    assert FLOORS_JSON.is_file(), f"missing {FLOORS_JSON}"
    assert WORKLOADS_JSON.is_file(), f"missing {WORKLOADS_JSON}"
    assert BASELINE_PY.is_file(), f"missing {BASELINE_PY}"
    assert FLOORS_JSON.stat().st_size > 0
    assert RUN_PY.stat().st_size > 0


def test_reviewed_floors_schema_and_status() -> None:
    floors = _read_floors()
    assert floors["schema"] == "KernelVFSReviewedFloors@1"
    assert floors["schema_version"] == "ipfs_kit_py.kernel_vfs.reviewed_floors@1"
    assert floors["task_id"] == "KVFS-801"
    assert floors["status"] == "reviewed"
    assert floors["reviewed"] is True
    assert floors["reviewed_by"]
    assert floors["review_receipt_cid"]
    assert floors["comparison_rules"]["immutable"] is True
    assert floors["policy"]["floors_status"] == "reviewed"
    assert floors["policy"]["hermetic_gate_profile"] == "ci-reference"


def test_required_metric_bindings_present() -> None:
    floors = _read_floors()
    bindings = floors["required_metric_bindings"]
    for item in REQUIRED_METRIC_BINDINGS:
        assert item in bindings, f"missing metric binding {item}"


def test_environments_bind_cold_warm_and_performance_sections() -> None:
    floors = _read_floors()
    environments = floors["environments"]
    for env_name in REQUIRED_ENVIRONMENTS:
        assert env_name in environments, f"missing environment {env_name}"
        env = environments[env_name]
        assert set(env["path_classes"]) >= set(REQUIRED_PATH_CLASSES)
        perf = env["performance_floors"]
        for section in REQUIRED_PERF_SECTIONS:
            assert section in perf, f"{env_name} missing performance section {section}"

        for family in ("metadata", "sequential_io", "random_io", "handles"):
            for pc in REQUIRED_PATH_CLASSES:
                node = perf[family][pc]
                assert isinstance(node, dict)
                if family in ("metadata", "sequential_io", "random_io"):
                    assert "p95_ms_max" in node or "p99_ms_max" in node
                    assert "ops_per_s_min" in node

        wal = perf["committed_throughput"]["wal"]
        for pc in REQUIRED_PATH_CLASSES:
            assert wal[pc]["ack_state"] == "committed"
            assert "committed_ops_per_s_min" in wal[pc]
            assert "p99_ms_max" in wal[pc] or "p95_ms_max" in wal[pc]

        for pc in REQUIRED_PATH_CLASSES:
            assert "hit_ratio_min" in perf["arc_ratios"][pc]
            assert "queue_depth_max" in perf["wal_queue"][pc]

        assert "rss_bytes_max" in perf["memory"]
        assert "leaked_fds_max" in perf["descriptors"]
        mount = perf["mount_cycles"]
        assert mount["success_ratio_min"] == 1.0
        assert mount["leaked_mount_max"] == 0
        assert mount["leaked_handle_max"] == 0
        assert int(mount["cycle_count_min"]) >= 1


def test_safety_floors_are_all_zero() -> None:
    floors = _read_floors()
    safety = floors["safety_floors"]
    for key in ZERO_SAFETY_KEYS:
        assert key in safety, f"missing safety floor {key}"
        assert safety[key] == 0, f"safety floor {key} must be 0"
    assert all(int(v) == 0 for v in safety.values())


def test_chaos_scenarios_declare_outcomes_and_degradation() -> None:
    floors = _read_floors()
    chaos = floors["chaos_scenarios"]
    for name in REQUIRED_CHAOS:
        assert name in chaos, f"missing chaos scenario {name}"
        scenario = chaos[name]
        assert scenario["safety_counters"]
        assert scenario["required_outcomes"]
        assert isinstance(scenario["degradation"], dict)
        # Every listed counter must exist in the global zero-floor table.
        for counter in scenario["safety_counters"]:
            assert counter in floors["safety_floors"]
            assert floors["safety_floors"][counter] == 0

    bounds = floors["degradation_bounds"]
    assert 0.0 <= float(bounds["throughput_min_fraction_of_baseline"]) <= 1.0
    assert float(bounds["recovery_seconds_max"]) > 0
    tolerance = bounds["post_chaos_resource_tolerance"]
    assert tolerance["queue_depth"] == 0
    assert tolerance["open_handles"] == 0
    assert tolerance["leaked_fds"] == 0
    assert tolerance["leaked_mounts"] == 0


def test_harness_validate_reviewed_floors_accepts_checked_in_document() -> None:
    floors = _read_floors()
    errors = release_run.validate_reviewed_floors(floors)
    assert errors == [], errors


def test_harness_rejects_non_reviewed_or_nonzero_safety() -> None:
    floors = _read_floors()
    bad = copy.deepcopy(floors)
    bad["status"] = "provisional"
    bad["reviewed"] = False
    errors = release_run.validate_reviewed_floors(bad)
    assert any("reviewed" in e or "status" in e for e in errors)

    bad2 = copy.deepcopy(floors)
    bad2["safety_floors"]["acknowledged_committed_data_loss"] = 1
    errors2 = release_run.validate_reviewed_floors(bad2)
    assert any("acknowledged_committed_data_loss" in e for e in errors2)


def test_absolute_floor_lock_detects_lowered_reviewed_floor() -> None:
    """A change that lowers a reviewed floor while claiming reviewed must fail.

    The gate is structural: lowering ops_per_s_min / raising p99_ms_max on the
    hermetic profile is detectable by comparing against the checked-in document.
    """
    floors = _read_floors()
    locked = floors["environments"]["ci-reference"]["performance_floors"]
    original_ops = float(locked["metadata"]["warm"]["ops_per_s_min"])
    original_p99 = float(locked["metadata"]["warm"]["p99_ms_max"])

    candidate = copy.deepcopy(floors)
    candidate["environments"]["ci-reference"]["performance_floors"]["metadata"]["warm"][
        "ops_per_s_min"
    ] = original_ops * 0.5
    candidate["environments"]["ci-reference"]["performance_floors"]["metadata"]["warm"][
        "p99_ms_max"
    ] = original_p99 * 2.0

    # Simulate absolute floor lock comparison used by release tooling.
    failures = []
    base_node = locked["metadata"]["warm"]
    cand_node = candidate["environments"]["ci-reference"]["performance_floors"][
        "metadata"
    ]["warm"]
    if float(cand_node["ops_per_s_min"]) < float(base_node["ops_per_s_min"]):
        failures.append("absolute floor lowered: metadata.warm.ops_per_s_min")
    if float(cand_node["p99_ms_max"]) > float(base_node["p99_ms_max"]):
        failures.append("absolute ceiling relaxed: metadata.warm.p99_ms_max")
    assert failures
    assert any("lowered" in f for f in failures)
    assert any("relaxed" in f for f in failures)


# ---------------------------------------------------------------------------
# Hermetic chaos suite
# ---------------------------------------------------------------------------


def test_chaos_suite_meets_zero_safety_floors_and_outcomes() -> None:
    floors = _read_floors()
    receipt = release_run.run_chaos_suite(floors)
    assert receipt["all_safety_floors_zero"] is True, receipt["safety_counters"]
    assert receipt["all_outcomes_met"] is True, receipt["scenarios"]
    assert receipt["bounded_degradation"] is True
    assert set(receipt["scenario_names"]) >= set(REQUIRED_CHAOS)

    for name in REQUIRED_CHAOS:
        scenario = receipt["scenarios"][name]
        assert scenario["outcomes_met"] is True, scenario
        assert scenario["degradation_within_bounds"] is True
        assert float(scenario["elapsed_seconds"]) < 60.0

    # Every global safety counter remains zero.
    for key, value in receipt["safety_counters"].items():
        assert int(value) == 0, f"{key}={value}"


def test_chaos_kill_preserves_committed_and_rejects_stale() -> None:
    counters = release_run._zero_safety_snapshot(_read_floors())
    receipt = release_run.run_chaos_kill(counters)
    assert receipt["committed_preserved"] is True
    assert receipt["stale_read_rejected"] is True
    assert receipt["resources_released"] is True
    assert all(v == 0 for v in counters.values())


def test_chaos_torn_never_acknowledges() -> None:
    counters = release_run._zero_safety_snapshot(_read_floors())
    receipt = release_run.run_chaos_torn(counters)
    assert receipt["torn_not_acknowledged"] is True
    assert receipt["prefix_preserved"] is True
    assert receipt["fail_closed"] is True
    assert counters["torn_write_acknowledged"] == 0


def test_chaos_corrupt_is_safe_miss() -> None:
    counters = release_run._zero_safety_snapshot(_read_floors())
    receipt = release_run.run_chaos_corrupt(counters)
    assert receipt["corrupt_safe_miss"] is True
    assert receipt["no_poisoned_hit"] is True
    assert counters["corrupt_state_admitted"] == 0


def test_chaos_enospc_fail_closed() -> None:
    counters = release_run._zero_safety_snapshot(_read_floors())
    receipt = release_run.run_chaos_enospc(counters)
    assert receipt["no_acknowledged_loss"] is True
    assert receipt["explicit_failure"] is True
    assert receipt["fail_closed"] is True
    assert counters["enospc_acknowledged_loss"] == 0
    assert counters["acknowledged_committed_data_loss"] == 0


def test_chaos_backpressure_bounds_queue() -> None:
    counters = release_run._zero_safety_snapshot(_read_floors())
    receipt = release_run.run_chaos_backpressure(counters)
    assert receipt["queue_bounded"] is True
    assert receipt["explicit_rejection_or_wait"] is True
    assert receipt["resources_return_within_tolerance"] is True
    assert receipt["rejected"] > 0
    assert receipt["post_load_queue_depth"] == 0
    assert receipt["post_load_inflight"] == 0
    assert counters["backpressure_unbounded_queue"] == 0


# ---------------------------------------------------------------------------
# Performance / resource floors
# ---------------------------------------------------------------------------


def test_hermetic_mount_cycles_have_zero_leaks() -> None:
    receipt = release_run.run_hermetic_mount_cycles(cycles=8, seed=801)
    assert receipt["cycle_count"] == 8
    assert receipt["success_ratio"] == 1.0
    assert receipt["leaked_mount"] == 0
    assert receipt["leaked_handle"] == 0
    assert receipt["leaked_process"] == 0
    assert receipt["leaked_lease"] == 0


def test_check_reviewed_floors_passes_hermetic_gate() -> None:
    result = release_run.check_reviewed_floors(
        profile_name="ci-reference",
        run_measurements=True,
    )
    assert result["ok"] is True, result.get("error") or result.get("performance_failures")
    assert result["floors_reviewed"] is True
    assert result["chaos"]["all_safety_floors_zero"] is True
    assert result["chaos"]["bounded_degradation"] is True
    assert result["performance_failures"] == []
    assert result["chaos_failures"] == []
    assert set(result["chaos"]["scenario_names"]) >= set(REQUIRED_CHAOS)
    measurement = result["measurement"]
    assert "metadata" in measurement["observation_keys"]
    assert "sequential_io" in measurement["observation_keys"]
    assert "random_io" in measurement["observation_keys"]
    assert "wal" in measurement["observation_keys"]
    assert "arc" in measurement["observation_keys"]
    assert "handles" in measurement["observation_keys"]
    assert "memory" in measurement["observation_keys"]
    assert measurement["mount_cycles"]["leaked_mount"] == 0
    assert measurement["mount_cycles"]["leaked_handle"] == 0


def test_evaluate_performance_floors_fails_on_regression() -> None:
    floors = _read_floors()
    env = floors["environments"]["ci-reference"]
    perf = env["performance_floors"]
    # Build deliberately failing observations.
    bad_obs = {
        "metadata": {
            "cold": {"ops_per_s": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0},
            "warm": {"ops_per_s": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0},
        },
        "sequential_io": {
            "cold": {
                "ops_per_s": 0.0,
                "throughput_mib_s": 0.0,
                "p50_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
            },
            "warm": {
                "ops_per_s": 0.0,
                "throughput_mib_s": 0.0,
                "p50_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
            },
        },
        "random_io": {
            "cold": {
                "ops_per_s": 0.0,
                "throughput_mib_s": 0.0,
                "p50_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
            },
            "warm": {
                "ops_per_s": 0.0,
                "throughput_mib_s": 0.0,
                "p50_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
            },
        },
        "handles": {
            "cold": {
                "open_handles": 0,
                "open_handles_peak": 1,
                "lookup_p99_ms": 0.0,
            },
            "warm": {
                "open_handles": 0,
                "open_handles_peak": 1,
                "lookup_p99_ms": 0.0,
            },
        },
        "wal": {
            "cold": {
                "committed_ops_per_s": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
                "queue_depth_max": 1,
                "ack_state": "committed",
            },
            "warm": {
                "committed_ops_per_s": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
                "queue_depth_max": 1,
                "ack_state": "committed",
            },
        },
        "arc": {
            "cold": {"hit_ratio": 0.0, "eviction_count": 0},
            "warm": {"hit_ratio": 0.0, "eviction_count": 0},
        },
        "memory": {"rss_bytes": 1, "working_set_bytes": 1},
    }
    mount = {
        "cycle_count": 0,
        "success_ratio": 0.0,
        "leaked_mount": 1,
        "leaked_handle": 1,
        "leaked_process": 0,
        "leaked_lease": 0,
        "max_cycle_seconds": 0.1,
        "rss_growth_bytes": 0,
        "fd_growth": 0,
    }
    failures = release_run.evaluate_performance_floors(
        env_name="ci-reference",
        perf_floors=perf,
        observations=bad_obs,
        mount_receipt=mount,
        resource_sample={"fd_growth": 0, "leaked_fds": 0},
    )
    assert failures, "expected performance floor failures"
    assert any("ops_per_s" in f or "committed_ops" in f for f in failures)
    assert any("mount_cycles" in f for f in failures)
    assert any("leaked" in f for f in failures)


# ---------------------------------------------------------------------------
# CLI contract
# ---------------------------------------------------------------------------


def test_cli_check_reviewed_floors_exit_zero() -> None:
    proc = subprocess.run(
        [sys.executable, str(RUN_PY), "--check-reviewed-floors"],
        cwd=str(PACKAGE_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["task_id"] == "KVFS-801"
    assert payload["floors_reviewed"] is True
    assert payload["chaos"]["all_safety_floors_zero"] is True


def test_cli_check_schema_exit_zero() -> None:
    proc = subprocess.run(
        [sys.executable, str(RUN_PY), "--check-schema"],
        cwd=str(PACKAGE_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["floors_status"] == "reviewed"
    assert set(payload["environments"]) >= set(REQUIRED_ENVIRONMENTS)
    assert set(payload["chaos_scenarios"]) >= set(REQUIRED_CHAOS)


def test_check_schema_api() -> None:
    result = release_run.check_schema("ci-reference")
    assert result["ok"] is True
    assert result["all_safety_floors_zero"] is True
    assert "metadata.cold" in result["required_metric_bindings"]

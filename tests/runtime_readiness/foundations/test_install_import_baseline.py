"""Regression coverage for KITA-004 install/import/workload/TPS baselines."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Resolve nested package root (ipfs_kit_py/) from this test file.
# tests/runtime_readiness/foundations/ -> parents[3] == package root
PACKAGE_ROOT = Path(__file__).resolve().parents[3]
BENCH_DIR = PACKAGE_ROOT / "benchmarks" / "runtime_readiness"
BASELINE_PY = BENCH_DIR / "baseline.py"
WORKLOADS_JSON = BENCH_DIR / "workloads.json"
FLOORS_JSON = BENCH_DIR / "reference_floors.json"

# Make the harness importable without installing.
if str(BENCH_DIR) not in sys.path:
    sys.path.insert(0, str(BENCH_DIR))
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

import baseline as baseline_mod  # noqa: E402  (path setup above)


# ---------------------------------------------------------------------------
# Artifact presence
# ---------------------------------------------------------------------------


def test_declared_baseline_artifacts_exist():
    assert BASELINE_PY.is_file(), f"missing {BASELINE_PY}"
    assert WORKLOADS_JSON.is_file(), f"missing {WORKLOADS_JSON}"
    assert FLOORS_JSON.is_file(), f"missing {FLOORS_JSON}"


def test_workloads_schema_and_required_profiles():
    data = json.loads(WORKLOADS_JSON.read_text(encoding="utf-8"))
    assert data["schema"] == "WorkloadProfile@1"
    assert "ci-reference" in data["resource_profiles"]
    for path_class in ("cold", "warm", "cache"):
        assert path_class in data["path_classes"]
    for ack in ("accepted", "committed", "converged"):
        assert ack in data["ack_states"]
    # Plan-pinned workload families
    for wl in (
        "metadata_txn",
        "small_object_txn",
        "mixed_vfs",
        "wal_commit",
        "arc_hotset",
        "graphrag_query",
        "replica_reconcile",
        "interface_roundtrip",
        "cold_import_root",
        "cold_import_mcp",
        "install_wheel_probe",
    ):
        assert wl in data["workloads"], f"missing workload {wl}"
    # Identity binding for immutable comparison
    binding = data["comparison_binding"]
    for field in (
        "hardware",
        "os",
        "python",
        "dependencies",
        "revision",
        "dataset",
        "seed",
        "concurrency",
        "durability",
        "warmup",
        "samples",
        "confidence",
    ):
        assert field in binding["identity_fields"]
    assert binding["primary_throughput_metric"] == "committed_tps"


def test_reference_floors_are_explicitly_provisional():
    data = json.loads(FLOORS_JSON.read_text(encoding="utf-8"))
    assert data["schema"] == "RuntimeReferenceFloors@1"
    assert data["status"] == "provisional"
    assert data["reviewed"] is False
    assert data["review_receipt_cid"] is None
    rules = data["comparison_rules"]
    assert rules["immutable"] is True
    assert rules["rule_id"] == "RuntimeComparisonRules@1"
    rule_ids = {r["id"] for r in rules["rules"]}
    assert "committed_not_accepted" in rule_ids
    assert "path_class_separation" in rule_ids
    assert "absolute_floor_lock" in rule_ids
    assert "provisional_non_gate" in rule_ids
    # No transaction-specific SLO at this task
    txn = data["observation_anchors"]["transaction_specific_slo"]
    assert txn["slo_present"] is False
    assert txn["status"] == "absent"


def test_observation_anchors_capture_known_defects():
    data = json.loads(FLOORS_JSON.read_text(encoding="utf-8"))
    anchors = data["observation_anchors"]
    assert anchors["root_eager_imports"]["status"] == "observed"
    assert anchors["mcp_eager_imports"]["status"] == "observed"
    assert anchors["runtime_metadata_version_mismatch"]["status"] == "observed"
    assert anchors["dependency_projection_drift"]["status"] == "observed"


# ---------------------------------------------------------------------------
# Harness API
# ---------------------------------------------------------------------------


def test_check_schema_ci_reference_ok():
    report = baseline_mod.check_schema("ci-reference")
    assert report["ok"] is True
    assert report["schema"] == "RuntimeBenchmarkManifest@1"
    assert report["floors_status"] == "provisional"
    assert report["comparison_rules_immutable"] is True
    assert report["primary_throughput_metric"] == "committed_tps"
    assert report["transaction_specific_slo_present"] is False
    assert set(report["path_classes"]) == {"cache", "cold", "warm"}
    for field in baseline_mod.REQUIRED_IDENTITY_FIELDS:
        assert field in report["identity_fields"]
    assert report["micro_committed_tps"] > 0
    assert report["micro_accepted_tps"] > 0
    # Committed must not exceed accepted in the micro model (diagnostic).
    assert report["micro_committed_tps"] <= report["micro_accepted_tps"] * 1.05


def test_identity_records_all_required_fields():
    workloads = baseline_mod.load_workloads()
    profile = workloads["resource_profiles"]["ci-reference"]
    identity = baseline_mod.build_identity(
        profile=profile,
        seed=int(profile["default_seed"]),
        concurrency=int(profile["default_concurrency"]),
        durability=str(profile["default_durability"]),
        warmup=int(profile["warmup_samples"]),
        samples=int(profile["measurement_samples"]),
        confidence=float(profile["confidence_level"]),
        dataset="dataset:metadata_catalog_v1",
        package_root=PACKAGE_ROOT,
    )
    for field in baseline_mod.REQUIRED_IDENTITY_FIELDS:
        assert field in identity, f"identity missing {field}"
    assert "identity_digest" in identity
    assert identity["seed"] == profile["default_seed"]
    assert identity["concurrency"] == profile["default_concurrency"]
    assert identity["durability"] == profile["default_durability"]
    assert identity["warmup"] == profile["warmup_samples"]
    assert identity["samples"] == profile["measurement_samples"]
    assert identity["confidence"] == profile["confidence_level"]
    assert "version" in identity["python"]
    assert "system" in identity["os"]
    assert "machine" in identity["hardware"]
    assert "declared_digest" in identity["dependencies"]


def test_observations_capture_version_mismatch_and_drift():
    obs = baseline_mod.build_observations(PACKAGE_ROOT)
    assert "runtime_metadata_version_mismatch" in obs
    assert "dependency_projection_drift" in obs
    assert "root_eager_imports" in obs
    assert "mcp_eager_imports" in obs
    assert obs["no_transaction_specific_slo"]["slo_present"] is False
    # Bound revision has known runtime vs metadata mismatch (0.2.0 vs 0.3.0).
    versions = baseline_mod.capture_metadata_versions(PACKAGE_ROOT)
    assert versions["runtime_version"] is not None
    assert versions["pyproject_version"] is not None
    # Document the mismatch when present; do not "fix" it in this task.
    if versions["runtime_version"] != versions["pyproject_version"]:
        assert versions["runtime_metadata_mismatch"] is True
        assert obs["runtime_metadata_version_mismatch"]["observed"] is True


def test_mcp_eager_import_static_analysis_flags_eventdag():
    eager = baseline_mod.analyze_eager_imports_from_source(PACKAGE_ROOT)
    assert eager["mcp_server_exists"] is True
    assert eager["root_init_exists"] is True
    # Confirmed baseline blocker: EventDAGStore used without import.
    assert eager["mcp_eventdag_unimported_reference"] is True
    assert isinstance(eager["mcp_eager_import_lines"], list)
    assert isinstance(eager["root_eager_import_lines"], list)


def test_transaction_measurement_distinguishes_committed_and_accepted():
    result = baseline_mod.measure_transaction_workload(
        operations=["put", "get", "delete"],
        seed=424242,
        warmup=2,
        samples=20,
        payload_bytes=64,
        durability="memory_sync",
        path_class="warm",
        confidence=0.95,
    )
    assert result["primary_metric"] == "committed_tps"
    assert result["committed_tps"] > 0
    assert result["accepted_tps"] > 0
    assert "committed_latency_ms" in result
    assert "accepted_latency_ms" in result
    for key in ("p50", "p95", "p99"):
        assert key in result["committed_latency_ms"]
    assert result["partial"] is False
    assert result["errors"] == 0
    assert set(result["ack_states_measured"]) == {"accepted", "committed"}
    # Committed path includes durability barrier; latency should be >= accepted.
    assert (
        result["committed_latency_ms"]["p50"]
        >= result["accepted_latency_ms"]["p50"] * 0.99
    )


def test_path_classes_cold_warm_cache_are_separated():
    common = dict(
        operations=["put", "get"],
        seed=7,
        samples=15,
        payload_bytes=64,
        durability="memory_sync",
        confidence=0.95,
    )
    cold = baseline_mod.measure_transaction_workload(
        **common, warmup=0, path_class="cold"
    )
    warm = baseline_mod.measure_transaction_workload(
        **common, warmup=5, path_class="warm"
    )
    cache = baseline_mod.measure_transaction_workload(
        **common, warmup=5, path_class="cache"
    )
    assert cold["path_class"] == "cold"
    assert warm["path_class"] == "warm"
    assert cache["path_class"] == "cache"
    # Results are labeled distinctly; comparison rules reject cross-class compare.
    left = {
        "identity": {"seed": 7, "dataset": "d", "concurrency": 1, "durability": "memory_sync",
                     "warmup": 0, "samples": 15, "confidence": 0.95,
                     "hardware": {"machine": "x", "cpu_count_logical": 1},
                     "os": {"system": "Linux", "release": "1"},
                     "python": {"version": "3.12.0"},
                     "dependencies": {"declared_digest": "a"},
                     "revision": {"git_commit": "abc"}},
        "path_class": "cold",
    }
    right = dict(left)
    right["path_class"] = "cache"
    ok, reasons = baseline_mod.results_comparable(left, right)
    assert ok is False
    assert any("path_class" in r for r in reasons)


def test_comparison_rules_require_identity_match():
    base_id = {
        "hardware": {"machine": "x86_64", "cpu_count_logical": 4},
        "os": {"system": "Linux", "release": "6.1"},
        "python": {"version": "3.12.0"},
        "dependencies": {"declared_digest": "deadbeef"},
        "revision": {"git_commit": "f6a574375febbcf9a46fcd24bbc7bc5cfb551de5"},
        "dataset": "dataset:metadata_catalog_v1",
        "seed": 424242,
        "concurrency": 1,
        "durability": "memory_sync",
        "warmup": 5,
        "samples": 25,
        "confidence": 0.95,
    }
    left = {"identity": dict(base_id), "path_class": "warm"}
    right = {"identity": dict(base_id), "path_class": "warm"}
    ok, reasons = baseline_mod.results_comparable(left, right)
    assert ok is True
    assert reasons == []

    right_mismatch = {"identity": dict(base_id), "path_class": "warm"}
    right_mismatch["identity"]["seed"] = 0
    ok2, reasons2 = baseline_mod.results_comparable(left, right_mismatch)
    assert ok2 is False
    assert any("seed" in r for r in reasons2)


def test_manifest_schema_rejects_accepted_as_primary():
    workloads = baseline_mod.load_workloads()
    floors = baseline_mod.load_floors()
    profile = workloads["resource_profiles"]["ci-reference"]
    identity = baseline_mod.build_identity(
        profile=profile,
        seed=1,
        concurrency=1,
        durability="memory_sync",
        warmup=1,
        samples=5,
        confidence=0.95,
        dataset="dataset:empty",
        package_root=PACKAGE_ROOT,
    )
    bad = {
        "schema": baseline_mod.SCHEMA,
        "schema_version": baseline_mod.SCHEMA_VERSION,
        "task_id": baseline_mod.TASK_ID,
        "profile": "ci-reference",
        "identity": identity,
        "observations": baseline_mod.build_observations(PACKAGE_ROOT),
        "path_classes": workloads["path_classes"],
        "ack_states": workloads["ack_states"],
        "workloads": {},
        "results": {
            "metadata_txn": {
                "primary_metric": "committed_tps",
                "committed_tps": 10.0,
                "accepted_tps": 20.0,
                "path_class": "warm",
            }
        },
        "comparison_rules": {
            "immutable": True,
            "primary_throughput_metric": "accepted_tps",  # forbidden
            "rule_id": baseline_mod.COMPARISON_RULES_ID,
        },
        "floors_status": {"status": "provisional", "reviewed": False},
        "transaction_specific_slo": {"present": False},
    }
    problems = baseline_mod.validate_manifest_schema(bad)
    assert any("committed_tps" in p for p in problems)


def test_run_baseline_ci_reference_produces_valid_manifest():
    manifest = baseline_mod.run_baseline(
        "ci-reference",
        include_imports=False,  # keep unit test hermetic/fast
        include_transactions=True,
        package_root=PACKAGE_ROOT,
    )
    baseline_mod.assert_manifest_valid(manifest)
    assert manifest["floors_status"]["absolute_floors_provisional"] is True
    assert manifest["transaction_specific_slo"]["present"] is False
    assert manifest["comparison_rules"]["immutable"] is True
    assert manifest["comparison_rules"]["primary_throughput_metric"] == "committed_tps"
    # Transaction results stratified by path class
    meta = manifest["results"]["metadata_txn"]
    assert meta["primary_metric"] == "committed_tps"
    assert "by_path_class" in meta
    assert set(meta["by_path_class"]) >= {"cold", "warm", "cache"}
    for pc, payload in meta["by_path_class"].items():
        assert payload["path_class"] == pc
        assert "committed_tps" in payload
        assert "accepted_tps" in payload
    # Observations present
    assert manifest["observations"]["runtime_metadata_version_mismatch"]
    assert manifest["observations"]["dependency_projection_drift"]
    assert manifest["observations"]["root_eager_imports"]
    assert manifest["observations"]["mcp_eager_imports"]


def test_cli_check_schema_exit_zero():
    proc = subprocess.run(
        [
            sys.executable,
            str(BASELINE_PY),
            "--profile",
            "ci-reference",
            "--check-schema",
        ],
        cwd=str(PACKAGE_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    report = json.loads(proc.stdout)
    assert report["ok"] is True
    assert report["primary_throughput_metric"] == "committed_tps"
    assert report["floors_status"] == "provisional"
    assert report["transaction_specific_slo_present"] is False


def test_empty_samples_fail_closed():
    with pytest.raises(baseline_mod.BaselineMeasurementError):
        baseline_mod.measure_transaction_workload(
            operations=["put"],
            seed=1,
            warmup=0,
            samples=0,
            payload_bytes=8,
            durability="memory_sync",
            path_class="warm",
        )


def test_load_floors_requires_immutable_comparison_rules():
    floors = baseline_mod.load_floors()
    assert floors["comparison_rules"]["immutable"] is True
    assert (
        floors["observation_anchors"]["transaction_specific_slo"]["slo_present"]
        is False
    )


def test_resource_profiles_cover_plan_tiers():
    data = json.loads(WORKLOADS_JSON.read_text(encoding="utf-8"))
    profiles = data["resource_profiles"]
    for name in (
        "ci-reference",
        "memory-reference",
        "local-nvme",
        "local-daemon",
        "networked-provider",
    ):
        assert name in profiles
        p = profiles[name]
        assert "default_seed" in p
        assert "default_concurrency" in p
        assert "default_durability" in p
        assert "warmup_samples" in p
        assert "measurement_samples" in p
        assert "confidence_level" in p


def test_ack_committed_survives_crash_model_flag():
    data = json.loads(WORKLOADS_JSON.read_text(encoding="utf-8"))
    assert data["ack_states"]["committed"]["survives_declared_crash_model"] is True
    assert data["ack_states"]["accepted"]["survives_declared_crash_model"] is False

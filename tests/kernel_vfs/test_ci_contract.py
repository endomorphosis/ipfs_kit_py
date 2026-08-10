"""KVFS-802: CI contract for mandatory hermetic, native, Docker, and packaging gates.

Acceptance coverage:

* Core / VFS / WAL / ARC / FUSE / packaging / Docker path triggers fire the
  workflow;
* Python 3.12/3.13 Ubuntu and Windows hermetic tests are mandatory;
* capable Linux, self-hosted WinFsp, and Docker lanes emit receipts;
* zero collection, skip-only, stale receipt, permissive ``continue-on-error``,
  or shell ``|| true`` cannot pass a support gate.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Final, Iterable, Mapping

import pytest
import yaml

# tests/kernel_vfs -> parents[2] == package root (ipfs_kit_py/)
PACKAGE_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
WORKFLOW_PATH: Final[Path] = (
    PACKAGE_ROOT / ".github" / "workflows" / "kernel-vfs.yml"
)
TEST_PATH: Final[Path] = Path(__file__).resolve()

TASK_ID: Final[str] = "KVFS-802"
WORKFLOW_NAME: Final[str] = "Kernel VFS CI Gates"

REQUIRED_JOBS: Final[tuple[str, ...]] = (
    "ci-contract",
    "hermetic",
    "packaging",
    "linux-capable",
    "windows-winfsp",
    "docker-lane",
    "support-gate",
)

# Path-trigger categories required by acceptance.
PATH_TRIGGER_CATEGORIES: Final[dict[str, tuple[str, ...]]] = {
    "core": (
        "ipfs_kit_py/kernel_vfs/**",
        "ipfs_kit_py/core/vfs/**",
    ),
    "vfs": (
        "ipfs_kit_py/kernel_vfs/**",
        "ipfs_kit_py/core/vfs/**",
        "ipfs_kit_py/cli/kernel_vfs.py",
    ),
    "wal": (
        "ipfs_kit_py/core/wal/**",
        "ipfs_kit_py/kernel_vfs/wal_*.py",
        "ipfs_kit_py/kernel_vfs/durability.py",
        "tests/kernel_vfs/wal/**",
    ),
    "arc": (
        "ipfs_kit_py/kernel_vfs/cache_*.py",
        "ipfs_kit_py/kernel_vfs/cached_storage.py",
        "tests/kernel_vfs/arc/**",
    ),
    "fuse": (
        "ipfs_kit_py/kernel_vfs/linux.py",
        "ipfs_kit_py/kernel_vfs/windows.py",
        "ipfs_kit_py/kernel_vfs/winfsp_loader.py",
        "ipfs_kit_py/kernel_vfs/platform.py",
        "tests/kernel_vfs/linux/**",
        "tests/kernel_vfs/windows/**",
    ),
    "packaging": (
        "pyproject.toml",
        "tests/kernel_vfs/packaging/**",
    ),
    "docker": (
        "docker/kernel-vfs.Dockerfile",
        "docker-compose.kernel-vfs.yml",
        "tests/kernel_vfs/container/**",
    ),
}

MANDATORY_PYTHON: Final[frozenset[str]] = frozenset({"3.12", "3.13"})
MANDATORY_HERMETIC_OS: Final[frozenset[str]] = frozenset(
    {"ubuntu-latest", "windows-latest"}
)

# Patterns that must appear on support-critical jobs/steps (fail-closed).
ZERO_COLLECTION_MARKERS: Final[tuple[str, ...]] = (
    "no tests collected",
    "collected 0 items",
    "zero collection",
    "Guard against zero collection",
)
SKIP_ONLY_MARKERS: Final[tuple[str, ...]] = (
    "skip-only",
    "skip_only",
    "skipped,? 0 passed",
)
STALE_RECEIPT_MARKERS: Final[tuple[str, ...]] = (
    "stale receipt",
    "EXPECTED_COMMIT",
    "fresh",
    "unix_ms",
)
RECEIPT_EMIT_MARKERS: Final[tuple[str, ...]] = (
    "suite.json",
    "upload-artifact",
    "kvfs-receipt-",
)

# Shell / Actions patterns that must not soften support-critical failure.
PERMISSIVE_FAILURE_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"continue-on-error\s*:"),
    re.compile(r"\|\|\s*true\b"),
    re.compile(r"\|\|\s*:\s*$", re.MULTILINE),
)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _workflow_text() -> str:
    assert WORKFLOW_PATH.is_file(), f"missing workflow: {WORKFLOW_PATH}"
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert text.strip(), "workflow must not be empty"
    return text


def _workflow_doc() -> dict[str, Any]:
    doc = yaml.safe_load(_workflow_text())
    assert isinstance(doc, dict), "workflow must parse to a mapping"
    return doc


def _on_block(doc: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return the workflow ``on:`` trigger block.

    PyYAML 1.1 may coerce the key ``on`` to boolean ``True``.
    """
    for key in ("on", True, "true", "True"):
        if key in doc:
            value = doc[key]
            assert isinstance(value, Mapping), "on: must be a mapping"
            return value
    raise AssertionError("workflow missing on: trigger block")


def _jobs(doc: Mapping[str, Any]) -> dict[str, Any]:
    jobs = doc.get("jobs")
    assert isinstance(jobs, dict) and jobs, "workflow must declare jobs"
    return jobs


def _path_list(on_block: Mapping[str, Any], event: str) -> list[str]:
    event_cfg = on_block.get(event)
    assert isinstance(event_cfg, Mapping), f"on.{event} must be a mapping"
    paths = event_cfg.get("paths")
    assert isinstance(paths, list) and paths, f"on.{event}.paths must be a non-empty list"
    return [str(item) for item in paths]


def _all_trigger_paths(doc: Mapping[str, Any]) -> set[str]:
    on_block = _on_block(doc)
    paths: set[str] = set()
    for event in ("pull_request", "push"):
        paths.update(_path_list(on_block, event))
    return paths


def _matrix_values(job: Mapping[str, Any], key: str) -> set[str]:
    strategy = job.get("strategy") or {}
    assert isinstance(strategy, Mapping), "job strategy must be a mapping"
    matrix = strategy.get("matrix") or {}
    assert isinstance(matrix, Mapping), "job matrix must be a mapping"
    if key in matrix:
        values = matrix[key]
        assert isinstance(values, list), f"matrix.{key} must be a list"
        return {str(v) for v in values}
    # Support include-style matrices.
    include = matrix.get("include") or []
    found: set[str] = set()
    if isinstance(include, list):
        for row in include:
            if isinstance(row, Mapping) and key in row:
                found.add(str(row[key]))
    return found


def _job_runs_on(job: Mapping[str, Any]) -> Any:
    return job.get("runs-on")


def _flatten_strings(node: Any) -> list[str]:
    """Recursively collect string leaves from a YAML subtree."""
    if isinstance(node, str):
        return [node]
    if isinstance(node, Mapping):
        out: list[str] = []
        for key, value in node.items():
            out.append(str(key))
            out.extend(_flatten_strings(value))
        return out
    if isinstance(node, (list, tuple)):
        out = []
        for item in node:
            out.extend(_flatten_strings(item))
        return out
    return []


def _job_blob(job: Mapping[str, Any]) -> str:
    return "\n".join(_flatten_strings(job))


def _step_run_scripts(job: Mapping[str, Any]) -> list[str]:
    steps = job.get("steps") or []
    assert isinstance(steps, list), "job steps must be a list"
    scripts: list[str] = []
    for step in steps:
        if not isinstance(step, Mapping):
            continue
        run = step.get("run")
        if isinstance(run, str):
            scripts.append(run)
    return scripts


def _support_critical_jobs(jobs: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    """Jobs whose failure must not be softened (support gate inputs + gate)."""
    critical = {}
    for name in REQUIRED_JOBS:
        assert name in jobs, f"missing required job {name!r}"
        job = jobs[name]
        assert isinstance(job, Mapping), f"job {name!r} must be a mapping"
        critical[name] = job
    return critical


def _contains_any(blob: str, markers: Iterable[str]) -> bool:
    lower = blob.lower()
    for marker in markers:
        # Allow regex-ish markers with simple optional comma.
        if ",?" in marker:
            pattern = marker.replace(",?", r",?")
            if re.search(pattern, blob, flags=re.IGNORECASE):
                return True
            continue
        if marker.lower() in lower:
            return True
    return False


# ---------------------------------------------------------------------------
# Declared outputs / identity
# ---------------------------------------------------------------------------


def test_declared_outputs_exist() -> None:
    assert WORKFLOW_PATH.is_file()
    assert WORKFLOW_PATH.stat().st_size > 0
    assert TEST_PATH.is_file()
    assert TEST_PATH.stat().st_size > 0


def test_workflow_identity_and_task_markers() -> None:
    text = _workflow_text()
    doc = _workflow_doc()
    assert doc.get("name") == WORKFLOW_NAME
    assert TASK_ID in text
    assert "fail-closed" in text.lower() or "fail closed" in text.lower()
    assert "support gate" in text.lower() or "support-gate" in text


# ---------------------------------------------------------------------------
# Path triggers — Core / VFS / WAL / ARC / FUSE / packaging / Docker
# ---------------------------------------------------------------------------


def test_path_triggers_cover_required_categories() -> None:
    doc = _workflow_doc()
    paths = _all_trigger_paths(doc)
    missing: dict[str, list[str]] = {}
    for category, required in PATH_TRIGGER_CATEGORIES.items():
        absent = [item for item in required if item not in paths]
        if absent:
            missing[category] = absent
    assert not missing, f"path triggers missing required categories: {missing}"


def test_pull_request_and_push_share_path_triggers() -> None:
    doc = _workflow_doc()
    on_block = _on_block(doc)
    pr_paths = set(_path_list(on_block, "pull_request"))
    push_paths = set(_path_list(on_block, "push"))
    # Categories must trigger on both PR and push (release-ci).
    for category, required in PATH_TRIGGER_CATEGORIES.items():
        for item in required:
            assert item in pr_paths, f"PR paths missing {category} trigger {item!r}"
            assert item in push_paths, f"push paths missing {category} trigger {item!r}"


def test_workflow_self_path_is_trigger() -> None:
    paths = _all_trigger_paths(_workflow_doc())
    assert ".github/workflows/kernel-vfs.yml" in paths


# ---------------------------------------------------------------------------
# Job inventory
# ---------------------------------------------------------------------------


def test_required_jobs_present() -> None:
    jobs = _jobs(_workflow_doc())
    for name in REQUIRED_JOBS:
        assert name in jobs, f"missing required job: {name}"


# ---------------------------------------------------------------------------
# Mandatory hermetic matrix — Ubuntu + Windows × Python 3.12/3.13
# ---------------------------------------------------------------------------


def test_hermetic_job_is_mandatory_matrix() -> None:
    jobs = _jobs(_workflow_doc())
    hermetic = jobs["hermetic"]
    assert isinstance(hermetic, Mapping)

    # Must not be optional / soft-fail.
    assert "continue-on-error" not in hermetic

    os_values = _matrix_values(hermetic, "os")
    py_values = _matrix_values(hermetic, "python-version")
    assert MANDATORY_HERMETIC_OS <= os_values, (
        f"hermetic matrix must include {sorted(MANDATORY_HERMETIC_OS)}, got {sorted(os_values)}"
    )
    assert MANDATORY_PYTHON <= py_values, (
        f"hermetic matrix must include Python {sorted(MANDATORY_PYTHON)}, got {sorted(py_values)}"
    )

    blob = _job_blob(hermetic)
    assert "tests/kernel_vfs" in blob
    assert _contains_any(blob, ZERO_COLLECTION_MARKERS)
    assert _contains_any(blob, SKIP_ONLY_MARKERS)


def test_packaging_job_covers_python_and_os_matrix() -> None:
    jobs = _jobs(_workflow_doc())
    packaging = jobs["packaging"]
    assert isinstance(packaging, Mapping)
    assert "continue-on-error" not in packaging
    os_values = _matrix_values(packaging, "os")
    py_values = _matrix_values(packaging, "python-version")
    assert "ubuntu-latest" in os_values
    assert "windows-latest" in os_values
    assert MANDATORY_PYTHON <= py_values
    blob = _job_blob(packaging)
    assert "tests/kernel_vfs/packaging" in blob


# ---------------------------------------------------------------------------
# Capable lanes emit receipts
# -------------------------------------------------------------------------


def test_linux_capable_lane_emits_receipts_on_labeled_runner() -> None:
    jobs = _jobs(_workflow_doc())
    job = jobs["linux-capable"]
    assert isinstance(job, Mapping)
    runs_on = _job_runs_on(job)
    # Explicit labeled capability (conflict policy).
    assert isinstance(runs_on, list), "linux-capable must use labeled runs-on list"
    labels = {str(item).lower() for item in runs_on}
    assert "self-hosted" in labels
    assert "linux" in labels
    assert "fuse" in labels

    blob = _job_blob(job)
    assert "test_live_mount" in blob or "linux/test_live_mount" in blob
    assert _contains_any(blob, RECEIPT_EMIT_MARKERS)
    assert "suite.json" in blob
    assert "upload-artifact" in blob
    assert "kvfs-receipt-linux-capable" in blob
    assert "continue-on-error" not in job
    assert _contains_any(blob, ZERO_COLLECTION_MARKERS)


def test_windows_winfsp_lane_emits_receipts_on_self_hosted_labels() -> None:
    jobs = _jobs(_workflow_doc())
    job = jobs["windows-winfsp"]
    assert isinstance(job, Mapping)
    runs_on = _job_runs_on(job)
    assert isinstance(runs_on, list), "windows-winfsp must use labeled runs-on list"
    labels = {str(item).lower() for item in runs_on}
    assert "self-hosted" in labels
    assert "windows" in labels
    assert "winfsp" in labels

    blob = _job_blob(job)
    assert "test_live_winfsp" in blob or "windows/test_live_winfsp" in blob
    assert _contains_any(blob, RECEIPT_EMIT_MARKERS)
    assert "suite.json" in blob
    assert "kvfs-receipt-windows-winfsp" in blob
    assert "continue-on-error" not in job
    assert _contains_any(blob, ZERO_COLLECTION_MARKERS)


def test_docker_lane_emits_receipts() -> None:
    jobs = _jobs(_workflow_doc())
    job = jobs["docker-lane"]
    assert isinstance(job, Mapping)
    blob = _job_blob(job)
    assert "tests/kernel_vfs/container" in blob
    assert _contains_any(blob, RECEIPT_EMIT_MARKERS)
    assert "suite.json" in blob
    assert "kvfs-receipt-docker" in blob
    assert "continue-on-error" not in job
    assert _contains_any(blob, ZERO_COLLECTION_MARKERS)


# ---------------------------------------------------------------------------
# Support gate — fail-closed against soft failures
# ---------------------------------------------------------------------------


def test_support_gate_depends_on_all_lanes_and_is_always_evaluated() -> None:
    jobs = _jobs(_workflow_doc())
    gate = jobs["support-gate"]
    assert isinstance(gate, Mapping)
    needs = gate.get("needs")
    assert isinstance(needs, list), "support-gate must declare needs"
    for name in (
        "ci-contract",
        "hermetic",
        "packaging",
        "linux-capable",
        "windows-winfsp",
        "docker-lane",
    ):
        assert name in needs, f"support-gate must need {name!r}"
    # if: always() ensures a failed/skipped upstream still runs the gate.
    assert str(gate.get("if") or "").replace(" ", "") == "always()"
    assert "continue-on-error" not in gate


def test_support_gate_rejects_zero_collection_skip_only_and_stale_receipts() -> None:
    jobs = _jobs(_workflow_doc())
    gate = jobs["support-gate"]
    assert isinstance(gate, Mapping)
    blob = _job_blob(gate)
    scripts = "\n".join(_step_run_scripts(gate))

    assert _contains_any(blob, ZERO_COLLECTION_MARKERS) or "zero receipt" in scripts.lower()
    assert _contains_any(scripts, SKIP_ONLY_MARKERS) or "skip-only" in scripts.lower()
    assert _contains_any(scripts, STALE_RECEIPT_MARKERS)
    assert "EXPECTED_COMMIT" in scripts
    assert "EXPECTED_RUN_ID" in scripts
    assert "suite.json" in scripts
    assert "support_promoted" in scripts
    # Must download receipt artifacts and fail closed on missing lanes.
    assert "download-artifact" in blob
    assert "kvfs-receipt-" in blob
    assert "missing receipt" in scripts.lower() or "required lane" in scripts.lower()


def test_support_critical_jobs_forbid_continue_on_error() -> None:
    jobs = _jobs(_workflow_doc())
    critical = _support_critical_jobs(jobs)
    offenders: list[str] = []
    for name, job in critical.items():
        # Job-level continue-on-error is always forbidden.
        if "continue-on-error" in job:
            offenders.append(f"{name}: job-level continue-on-error")
        steps = job.get("steps") or []
        if not isinstance(steps, list):
            continue
        for index, step in enumerate(steps):
            if isinstance(step, Mapping) and "continue-on-error" in step:
                step_name = step.get("name") or f"step[{index}]"
                offenders.append(f"{name}: {step_name} continue-on-error")
    assert not offenders, (
        "continue-on-error cannot pass a support gate; offenders: " + "; ".join(offenders)
    )


def test_support_critical_scripts_forbid_permissive_true() -> None:
    """Shell ``|| true`` (and cousins) must not mask support-critical failures."""
    jobs = _jobs(_workflow_doc())
    critical = _support_critical_jobs(jobs)
    offenders: list[str] = []
    for name, job in critical.items():
        for index, script in enumerate(_step_run_scripts(job)):
            for pattern in PERMISSIVE_FAILURE_PATTERNS:
                if pattern.search(script):
                    offenders.append(
                        f"{name}: step[{index}] matches {pattern.pattern!r}"
                    )
    assert not offenders, (
        "permissive failure masking cannot pass a support gate; offenders: "
        + "; ".join(offenders)
    )


def test_workflow_text_has_no_support_gate_continue_on_error_or_or_true() -> None:
    """Belt-and-suspenders raw-text scan of the whole workflow file."""
    text = _workflow_text()
    # Strip comments so illustrative prose cannot false-positive.
    code_lines = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        # Keep inline code before a comment marker carefully: shell often uses #.
        code_lines.append(line)
    code = "\n".join(code_lines)

    assert "continue-on-error" not in code, (
        "continue-on-error is forbidden in kernel-vfs support workflow"
    )
    # Allow documentation strings that mention the forbidden pattern only inside
    # comments (already stripped). Active shell must not use || true.
    assert not re.search(r"\|\|\s*true\b", code), (
        "shell '|| true' is forbidden in kernel-vfs support workflow"
    )


def test_hermetic_and_capable_lanes_guard_zero_collection() -> None:
    jobs = _jobs(_workflow_doc())
    for name in ("hermetic", "packaging", "linux-capable", "windows-winfsp", "docker-lane"):
        job = jobs[name]
        assert isinstance(job, Mapping)
        blob = _job_blob(job)
        assert _contains_any(blob, ZERO_COLLECTION_MARKERS), (
            f"{name} must guard against zero collection"
        )
        scripts = "\n".join(_step_run_scripts(job))
        assert "--collect-only" in scripts, f"{name} must run collect-only guard"
        assert "exit 1" in scripts, f"{name} must fail closed on bad collection"


def test_receipts_are_commit_and_run_bound() -> None:
    text = _workflow_text()
    assert "KVFS_RECEIPT_COMMIT" in text
    assert "KVFS_RECEIPT_RUN_ID" in text
    assert "github.sha" in text
    assert "github.run_id" in text
    # Support gate must compare receipt identity to the current run.
    gate_scripts = "\n".join(_step_run_scripts(_jobs(_workflow_doc())["support-gate"]))
    assert "EXPECTED_COMMIT" in gate_scripts
    assert "EXPECTED_RUN_ID" in gate_scripts
    assert "stale receipt" in gate_scripts.lower()


def test_support_gate_cannot_promote_without_live_markers() -> None:
    scripts = "\n".join(_step_run_scripts(_jobs(_workflow_doc())["support-gate"]))
    assert "support_promoted" in scripts
    assert "live" in scripts
    # Fail-closed promotion check present in validator.
    assert "support_promoted without live" in scripts or (
        "support_promoted" in scripts and "live=true" in scripts.replace(" ", "")
    ) or ("not payload.get(\"live\")" in scripts or "not payload.get('live')" in scripts)


# ---------------------------------------------------------------------------
# Semantic unit of the support-gate validator policy (local, no GHA)
# ---------------------------------------------------------------------------


def _validate_receipts_for_gate(
    suite_payloads: list[dict[str, Any]],
    *,
    expected_commit: str,
    expected_run_id: str,
    now_ms: int,
) -> list[str]:
    """Mirror of the workflow support-gate receipt rules for unit coverage."""
    max_age_ms = 24 * 60 * 60 * 1000
    required_lane_tokens = {
        "hermetic": ("hermetic",),
        "packaging": ("packaging",),
        "linux-capable": ("linux-capable", "linux_capable", "linux"),
        "windows-winfsp": ("windows-winfsp", "windows_winfsp", "winfsp"),
        "docker": ("docker",),
    }
    errors: list[str] = []
    if not suite_payloads:
        return ["zero receipt collection: no suite.json artifacts"]

    seen_lanes: set[str] = set()
    for index, payload in enumerate(suite_payloads):
        label = f"receipt[{index}]"
        commit = str(payload.get("commit") or "")
        run_id = str(payload.get("run_id") or "")
        fresh = payload.get("fresh")
        unix_ms = payload.get("unix_ms")
        status = str(payload.get("status") or payload.get("gate_status") or "").lower()
        lane = str(payload.get("lane") or payload.get("profile") or "").lower()

        if commit != expected_commit:
            errors.append(f"{label}: stale receipt commit {commit!r}")
        if run_id != expected_run_id:
            errors.append(f"{label}: stale receipt run_id {run_id!r}")
        if fresh is False:
            errors.append(f"{label}: receipt marked fresh=false")
        if not isinstance(unix_ms, int):
            errors.append(f"{label}: missing integer unix_ms freshness stamp")
        elif now_ms - unix_ms > max_age_ms or unix_ms - now_ms > 5 * 60 * 1000:
            errors.append(f"{label}: stale receipt unix_ms={unix_ms}")
        if status in {"", "skipped", "skip-only", "skip_only", "zero_collection"}:
            errors.append(f"{label}: skip-only/empty status {status!r}")
        if payload.get("support_promoted") is True:
            if not payload.get("live"):
                errors.append(f"{label}: support_promoted without live=true is forbidden")
            claim = str(payload.get("support_claim") or "").lower()
            if claim not in {"live_passed", "passed", "admitted"}:
                errors.append(f"{label}: support_promoted with non-live claim {claim!r}")
        for required, tokens in required_lane_tokens.items():
            if any(token in lane for token in tokens):
                seen_lanes.add(required)

    for required in required_lane_tokens:
        if required not in seen_lanes:
            errors.append(f"missing receipt for required lane: {required}")
    return errors


def _fresh_receipt(
    lane: str,
    *,
    commit: str = "abc123",
    run_id: str = "42",
    now_ms: int = 1_700_000_000_000,
    **overrides: Any,
) -> dict[str, Any]:
    base = {
        "schema": "KernelVFSLaneReceipt@1",
        "lane": lane,
        "status": "passed",
        "support_claim": "hermetic_only",
        "support_promoted": False,
        "live": False,
        "commit": commit,
        "run_id": run_id,
        "unix_ms": now_ms,
        "fresh": True,
    }
    base.update(overrides)
    return base


def test_support_gate_policy_accepts_current_complete_receipt_set() -> None:
    now = 1_700_000_000_000
    payloads = [
        _fresh_receipt("hermetic", now_ms=now),
        _fresh_receipt("packaging", now_ms=now),
        _fresh_receipt("linux_capable", now_ms=now, status="capability_unavailable"),
        _fresh_receipt("windows_winfsp", now_ms=now, status="capability_unavailable"),
        _fresh_receipt("docker", now_ms=now, status="capability_unavailable"),
    ]
    errors = _validate_receipts_for_gate(
        payloads, expected_commit="abc123", expected_run_id="42", now_ms=now
    )
    assert errors == []


def test_support_gate_policy_rejects_zero_collection() -> None:
    errors = _validate_receipts_for_gate(
        [], expected_commit="abc123", expected_run_id="42", now_ms=1_700_000_000_000
    )
    assert any("zero receipt collection" in err for err in errors)


def test_support_gate_policy_rejects_skip_only_status() -> None:
    now = 1_700_000_000_000
    payloads = [
        _fresh_receipt("hermetic", now_ms=now, status="skip-only"),
        _fresh_receipt("packaging", now_ms=now),
        _fresh_receipt("linux_capable", now_ms=now),
        _fresh_receipt("windows_winfsp", now_ms=now),
        _fresh_receipt("docker", now_ms=now),
    ]
    errors = _validate_receipts_for_gate(
        payloads, expected_commit="abc123", expected_run_id="42", now_ms=now
    )
    assert any("skip-only" in err for err in errors)


def test_support_gate_policy_rejects_stale_receipt_commit() -> None:
    now = 1_700_000_000_000
    payloads = [
        _fresh_receipt("hermetic", now_ms=now, commit="old-sha"),
        _fresh_receipt("packaging", now_ms=now),
        _fresh_receipt("linux_capable", now_ms=now),
        _fresh_receipt("windows_winfsp", now_ms=now),
        _fresh_receipt("docker", now_ms=now),
    ]
    errors = _validate_receipts_for_gate(
        payloads, expected_commit="abc123", expected_run_id="42", now_ms=now
    )
    assert any("stale receipt commit" in err for err in errors)


def test_support_gate_policy_rejects_stale_run_id_and_old_unix_ms() -> None:
    now = 1_700_000_000_000
    payloads = [
        _fresh_receipt("hermetic", now_ms=now, run_id="1"),
        _fresh_receipt("packaging", now_ms=now - (25 * 60 * 60 * 1000)),
        _fresh_receipt("linux_capable", now_ms=now),
        _fresh_receipt("windows_winfsp", now_ms=now),
        _fresh_receipt("docker", now_ms=now),
    ]
    errors = _validate_receipts_for_gate(
        payloads, expected_commit="abc123", expected_run_id="42", now_ms=now
    )
    assert any("stale receipt run_id" in err for err in errors)
    assert any("stale receipt unix_ms" in err for err in errors)


def test_support_gate_policy_rejects_support_promoted_without_live() -> None:
    now = 1_700_000_000_000
    payloads = [
        _fresh_receipt("hermetic", now_ms=now),
        _fresh_receipt("packaging", now_ms=now),
        _fresh_receipt(
            "linux_capable",
            now_ms=now,
            support_promoted=True,
            live=False,
            support_claim="live_passed",
        ),
        _fresh_receipt("windows_winfsp", now_ms=now),
        _fresh_receipt("docker", now_ms=now),
    ]
    errors = _validate_receipts_for_gate(
        payloads, expected_commit="abc123", expected_run_id="42", now_ms=now
    )
    assert any("support_promoted without live" in err for err in errors)


def test_support_gate_policy_rejects_missing_lane_receipt() -> None:
    now = 1_700_000_000_000
    payloads = [
        _fresh_receipt("hermetic", now_ms=now),
        _fresh_receipt("packaging", now_ms=now),
        _fresh_receipt("linux_capable", now_ms=now),
        # windows_winfsp intentionally missing
        _fresh_receipt("docker", now_ms=now),
    ]
    errors = _validate_receipts_for_gate(
        payloads, expected_commit="abc123", expected_run_id="42", now_ms=now
    )
    assert any("windows-winfsp" in err for err in errors)


@pytest.mark.parametrize(
    "soft_pattern",
    [
        "continue-on-error: true",
        "pytest -q tests || true",
        "run_tests || true",
    ],
)
def test_soft_failure_patterns_are_detected_by_contract(soft_pattern: str) -> None:
    """Document the forbidden patterns the contract rejects in workflow text."""
    assert any(p.search(soft_pattern) for p in PERMISSIVE_FAILURE_PATTERNS) or (
        "continue-on-error" in soft_pattern
    )

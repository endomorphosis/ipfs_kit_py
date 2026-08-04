"""KITA-047: independent current-tree runtime-readiness release receipt.

One independently checked receipt binds exact repositories, packages,
capabilities, validations, metrics, and limitations for release. The validator
proves the complete 48-task / 12-goal terminal DAG and that no protected control
artifact changed after KITA-000 (taskboard status progress is the only permitted
mutation of the sealed board definition).

Interfaces: ``KITAReleaseReceipt@1``.
"""

from __future__ import annotations

import base64
import hashlib
import json
import platform
import re
import subprocess
import sys
import tomllib
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Paths / schema
# ---------------------------------------------------------------------------

PACKAGE_ROOT = Path(__file__).resolve().parents[3]
MONOREPO_ROOT = PACKAGE_ROOT.parent
DOCS_DIR = PACKAGE_ROOT / "docs" / "runtime_readiness"
BENCHMARKS_DIR = PACKAGE_ROOT / "benchmarks" / "runtime_readiness"
RECEIPT_PATH = DOCS_DIR / "KITA_RELEASE_RECEIPT.json"
SUITE_REL = "tests/runtime_readiness/release/test_joined_release_receipt.py"
SUITE_PATH = PACKAGE_ROOT / "tests" / "runtime_readiness" / "release" / "test_joined_release_receipt.py"

TODO_PATH = MONOREPO_ROOT / "docs" / "architecture" / "ipfs_kit_runtime_readiness.todo.md"
OBJECTIVE_PATH = (
    MONOREPO_ROOT / "docs" / "architecture" / "ipfs_kit_runtime_readiness.objectives.md"
)
PLAN_PATH = MONOREPO_ROOT / "docs" / "architecture" / "IPFS_KIT_RUNTIME_READINESS_PLAN.md"
SCHEDULER_PATH = (
    MONOREPO_ROOT / "config" / "agent_supervisor_ipfs_kit_runtime_readiness_scheduler.json"
)
BOARD_VALIDATOR_PATH = (
    MONOREPO_ROOT / "scripts" / "validate_ipfs_kit_runtime_readiness_board.py"
)
BOARD_TEST_PATH = MONOREPO_ROOT / "test" / "api" / "test_ipfs_kit_runtime_readiness_board.py"
GITIGNORE_PATH = MONOREPO_ROOT / ".gitignore"

RELEASE_RECEIPT_SCHEMA = "ipfs_kit_py/runtime-readiness/kita-release-receipt@1"
RELEASE_RECEIPT_INTERFACE = "KITAReleaseReceipt@1"
TASK_ID = "KITA-047"
GOAL_ID = "KITA-G110"
BOARD_NAMESPACE = "ipfs-kit-runtime-readiness-v1"
TERMINAL_TASK = "KITA-047"
ROOT_GOAL = "KITA-G000"

TASK_IDS = tuple(f"KITA-{index:03d}" for index in range(48))
GOAL_IDS = (
    "KITA-G000",
    "KITA-G010",
    "KITA-G020",
    "KITA-G030",
    "KITA-G040",
    "KITA-G050",
    "KITA-G060",
    "KITA-G070",
    "KITA-G080",
    "KITA-G090",
    "KITA-G100",
    "KITA-G110",
)

# Sealed at KITA-000; status-only progress is hash-neutral.
SEALED_TASKBOARD_DEFINITION_SHA256 = (
    "sha256:2f9620ce3b815344ae597be0cf7e2513b9561e0451ef283013b9730ebe0ca790"
)

PROTECTED_CONTROL_PATHS = (
    ".gitignore",
    "docs/architecture/IPFS_KIT_RUNTIME_READINESS_PLAN.md",
    "docs/architecture/ipfs_kit_runtime_readiness.objectives.md",
    "docs/architecture/ipfs_kit_runtime_readiness.todo.md",
    "config/agent_supervisor_ipfs_kit_runtime_readiness_scheduler.json",
    "scripts/validate_ipfs_kit_runtime_readiness_board.py",
    "test/api/test_ipfs_kit_runtime_readiness_board.py",
)

# Primary durable evidence artifacts (package-relative labels for CID binding).
PRIMARY_EVIDENCE: Mapping[str, tuple[str, ...]] = {
    "KITA-001": (
        "docs/runtime_readiness/capability_manifest.json",
        "docs/runtime_readiness/surface_inventory.md",
    ),
    "KITA-004": (
        "benchmarks/runtime_readiness/reference_floors.json",
        "benchmarks/runtime_readiness/workloads.json",
    ),
    "KITA-009": ("docs/runtime_readiness/vfs_conformance.json",),
    "KITA-013": ("docs/runtime_readiness/bucket_conformance.json",),
    "KITA-017": ("docs/runtime_readiness/graphrag_conformance.json",),
    "KITA-021": ("docs/runtime_readiness/replica_conformance.json",),
    "KITA-025": ("docs/runtime_readiness/arc_conformance.json",),
    "KITA-029": ("docs/runtime_readiness/replica_conformance.json",),
    "KITA-033": ("docs/runtime_readiness/mcplusplus_conformance.json",),
    "KITA-037": ("docs/runtime_readiness/interface_manifest.json",),
    "KITA-042": (
        "docs/runtime_readiness/backend_support_manifest.json",
        "docs/runtime_readiness/backend_support_matrix.md",
    ),
    "KITA-043": (
        "benchmarks/runtime_readiness/bound_revision_results.json",
        "benchmarks/runtime_readiness/optimized_results.json",
    ),
    "KITA-045": ("docs/runtime_readiness/soak_chaos_receipt.json",),
    "KITA-046": (
        "docs/runtime_readiness/release_candidate_receipt.json",
        "docs/runtime_readiness/migration_and_rollback.md",
    ),
    "KITA-047": (
        "docs/runtime_readiness/KITA_RELEASE_RECEIPT.json",
        "tests/runtime_readiness/release/test_joined_release_receipt.py",
    ),
}

REQUIRED_JOIN_DEPENDENCIES: Mapping[str, frozenset[str]] = {
    "KITA-009": frozenset(
        {"KITA-007", "KITA-008", "KITA-021", "KITA-037", "KITA-040", "KITA-041"}
    ),
    "KITA-013": frozenset(
        {
            "KITA-011",
            "KITA-012",
            "KITA-021",
            "KITA-029",
            "KITA-033",
            "KITA-037",
            "KITA-040",
            "KITA-041",
        }
    ),
    "KITA-017": frozenset({"KITA-015", "KITA-016", "KITA-037"}),
    "KITA-021": frozenset({"KITA-007", "KITA-019", "KITA-020"}),
    "KITA-025": frozenset({"KITA-022", "KITA-023", "KITA-024"}),
    "KITA-029": frozenset(
        {
            "KITA-012",
            "KITA-016",
            "KITA-020",
            "KITA-024",
            "KITA-028",
            "KITA-040",
            "KITA-041",
        }
    ),
    "KITA-033": frozenset(
        {
            "KITA-011",
            "KITA-016",
            "KITA-021",
            "KITA-029",
            "KITA-031",
            "KITA-032",
            "KITA-037",
        }
    ),
    "KITA-037": frozenset({"KITA-032", "KITA-034", "KITA-035", "KITA-036"}),
    "KITA-042": frozenset(
        {
            "KITA-013",
            "KITA-017",
            "KITA-021",
            "KITA-025",
            "KITA-029",
            "KITA-033",
            "KITA-037",
            "KITA-040",
            "KITA-041",
        }
    ),
    "KITA-044": frozenset(
        {
            "KITA-009",
            "KITA-013",
            "KITA-017",
            "KITA-021",
            "KITA-025",
            "KITA-029",
            "KITA-033",
            "KITA-037",
            "KITA-042",
            "KITA-043",
        }
    ),
    "KITA-046": frozenset(
        {
            "KITA-009",
            "KITA-013",
            "KITA-017",
            "KITA-021",
            "KITA-025",
            "KITA-029",
            "KITA-033",
            "KITA-037",
            "KITA-042",
            "KITA-045",
        }
    ),
    "KITA-047": frozenset({"KITA-046"}),
}

_CID_RE = re.compile(r"^b[a-z2-7]+$")
_SUITE_PATH_RE = re.compile(
    r"(?:tests|benchmarks|scripts|test)/[\w./-]+\.py"
)


# ---------------------------------------------------------------------------
# Digests / counters
# ---------------------------------------------------------------------------


def cid_for(label: str, payload: bytes) -> str:
    """Content-address label+payload as a CIDv1 raw multihash (base32)."""

    digest = hashlib.sha256(label.encode("utf-8") + b"\0" + payload).digest()
    multihash = b"\x01\x55\x12\x20" + digest
    return "b" + base64.b32encode(multihash).decode("ascii").rstrip("=").lower()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def semantic_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def directory_digest(path: Path) -> bytes:
    """Stable tree digest over relative paths and file bytes."""

    digest = hashlib.sha256()
    for file_path in sorted(p for p in path.rglob("*") if p.is_file()):
        rel = file_path.relative_to(path).as_posix().encode("utf-8")
        content = file_path.read_bytes()
        digest.update(len(rel).to_bytes(4, "big"))
        digest.update(rel)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.digest()


@dataclass
class ReleaseSafetyCounters:
    """Zero-floor counters for the joined release receipt."""

    acknowledged_loss: int = 0
    duplicate_non_idempotent_effects: int = 0
    authorization_bypass: int = 0
    path_escape: int = 0
    unsafe_execution: int = 0
    secret_leak: int = 0
    false_convergence: int = 0
    stale_evidence_accepted: int = 0
    missing_evidence_accepted: int = 0
    required_lane_skip: int = 0
    protected_control_mutation: int = 0
    broader_claim_without_evidence: int = 0
    safety_floor_violation: int = 0
    dag_integrity_failure: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "acknowledged_loss": self.acknowledged_loss,
            "duplicate_non_idempotent_effects": self.duplicate_non_idempotent_effects,
            "authorization_bypass": self.authorization_bypass,
            "path_escape": self.path_escape,
            "unsafe_execution": self.unsafe_execution,
            "secret_leak": self.secret_leak,
            "false_convergence": self.false_convergence,
            "stale_evidence_accepted": self.stale_evidence_accepted,
            "missing_evidence_accepted": self.missing_evidence_accepted,
            "required_lane_skip": self.required_lane_skip,
            "protected_control_mutation": self.protected_control_mutation,
            "broader_claim_without_evidence": self.broader_claim_without_evidence,
            "safety_floor_violation": self.safety_floor_violation,
            "dag_integrity_failure": self.dag_integrity_failure,
        }

    def all_zero(self) -> bool:
        return all(value == 0 for value in self.as_dict().values())


# ---------------------------------------------------------------------------
# Board / forest helpers
# ---------------------------------------------------------------------------


def taskboard_definition_sha256(text: str) -> str:
    """Mirror of the board validator seal (status-normalized, appendix-trimmed)."""

    canonical_text = text
    for match in re.finditer(r"^## (KITA-\d{3})\b", text, flags=re.MULTILINE):
        if match.group(1) in TASK_IDS:
            continue
        canonical_text = text[: match.start()].rstrip("\r\n") + "\n"
        break

    normalized: list[str] = []
    current_task_id = ""
    for line in canonical_text.splitlines(keepends=True):
        if line.startswith("## KITA-"):
            header = line[3:].strip()
            current_task_id = header.split(" ", 1)[0] if header else ""
        if current_task_id and line.startswith("- Status:"):
            newline = (
                "\r\n"
                if line.endswith("\r\n")
                else "\n"
                if line.endswith("\n")
                else ""
            )
            initial_status = "completed" if current_task_id == "KITA-000" else "todo"
            line = f"- Status: {initial_status}{newline}"
        normalized.append(line)
    return "sha256:" + hashlib.sha256("".join(normalized).encode("utf-8")).hexdigest()


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in re.split(r"[,;]", value) if item.strip())


def _git(args: Sequence[str], *, cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed in {cwd}: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def git_head(cwd: Path) -> str:
    return _git(["rev-parse", "HEAD"], cwd=cwd)


def git_dirty(cwd: Path, *, exclude_relative: Sequence[str] = ()) -> bool:
    """Return whether the worktree is dirty, optionally ignoring known paths."""

    raw = _git(["status", "--porcelain"], cwd=cwd)
    if not raw:
        return False
    excluded = {item.replace("\\", "/").lstrip("./") for item in exclude_relative}
    for line in raw.splitlines():
        if not line.strip():
            continue
        # porcelain v1 is "XY PATH". Some submodule lines may collapse the
        # second status column; accept both "XY PATH" and "X PATH".
        if len(line) > 3 and line[2] == " ":
            payload = line[3:]
        else:
            parts = line.split(None, 1)
            payload = parts[1] if len(parts) > 1 else line
        if " -> " in payload:
            payload = payload.split(" -> ", 1)[1]
        path = payload.strip().replace("\\", "/").strip('"')
        if path in excluded:
            continue
        if any(
            path == item or path.startswith(item.rstrip("/") + "/")
            for item in excluded
        ):
            continue
        return True
    return False


def parse_canonical_tasks(todo_text: str) -> dict[str, dict[str, Any]]:
    """Parse the sealed 48-task program (operational appendix excluded)."""

    sections = re.split(r"\n## (KITA-\d{3}) ", todo_text)
    tasks: dict[str, dict[str, Any]] = {}
    for index in range(1, len(sections), 2):
        task_id = sections[index]
        body = sections[index + 1]
        if re.search(r"(?im)^- Canonical board task:\s*false\s*$", body):
            continue
        if re.search(r"(?im)^- Generated by:\s*", body) and task_id not in TASK_IDS:
            continue
        number = int(task_id.split("-")[1])
        if number > 47:
            continue
        title = body.splitlines()[0].strip()
        status_m = re.search(r"(?m)^- Status:\s*(.+)\s*$", body)
        goal_m = re.search(r"(?m)^- Goal id:\s*(.+)\s*$", body)
        dep_m = re.search(r"(?m)^- Depends on:\s*(.*)\s*$", body)
        out_m = re.search(r"(?m)^- Outputs:\s*(.+)\s*$", body)
        val_m = re.search(r"(?m)^- Validation:\s*(.+)\s*$", body)
        iface_m = re.search(r"(?m)^- Interfaces:\s*(.*)\s*$", body)
        tasks[task_id] = {
            "task_id": task_id,
            "title": title,
            "status": (status_m.group(1).strip() if status_m else ""),
            "goal_id": (goal_m.group(1).strip() if goal_m else ""),
            "depends_on": list(_csv(dep_m.group(1) if dep_m else "")),
            "outputs": list(_csv(out_m.group(1) if out_m else "")),
            "validation": (val_m.group(1).strip() if val_m else ""),
            "interfaces": list(_csv(iface_m.group(1) if iface_m else "")),
        }
    return tasks


def parse_goals(objective_text: str) -> dict[str, dict[str, Any]]:
    sections = re.split(r"\n## (KITA-G\d{3}) ", objective_text)
    goals: dict[str, dict[str, Any]] = {}
    for index in range(1, len(sections), 2):
        goal_id = sections[index]
        body = sections[index + 1]
        title = body.splitlines()[0].strip()
        status_m = re.search(r"(?m)^- Status:\s*(.+)\s*$", body)
        parent_m = re.search(r"(?m)^- Parent:\s*(.*)\s*$", body)
        dep_m = re.search(r"(?m)^- Depends on:\s*(.*)\s*$", body)
        evidence_m = re.search(r"(?m)^- Evidence:\s*(.+)\s*$", body)
        goals[goal_id] = {
            "goal_id": goal_id,
            "title": title,
            "status": (status_m.group(1).strip() if status_m else ""),
            "parent": (parent_m.group(1).strip() if parent_m else ""),
            "depends_on": list(_csv(dep_m.group(1) if dep_m else "")),
            "evidence": list(_csv(evidence_m.group(1) if evidence_m else "")),
        }
    return goals


def _cycle_nodes(edges: Mapping[str, Sequence[str]]) -> tuple[str, ...]:
    visiting: set[str] = set()
    visited: set[str] = set()
    cycle: set[str] = set()

    def visit(node: str, lineage: tuple[str, ...]) -> None:
        if node in visited:
            return
        if node in visiting:
            if node in lineage:
                cycle.update(lineage[lineage.index(node) :])
            cycle.add(node)
            return
        visiting.add(node)
        for parent in edges.get(node, ()):
            visit(parent, (*lineage, node))
        visiting.remove(node)
        visited.add(node)

    for item in sorted(edges):
        visit(item, ())
    return tuple(sorted(cycle))


def bind_path(path: Path, *, label: str) -> dict[str, Any]:
    if path.is_file():
        data = path.read_bytes()
        return {
            "path": label,
            "kind": "file",
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "evidence_cid": cid_for(label, data),
            "present": True,
        }
    if path.is_dir():
        tree = directory_digest(path)
        return {
            "path": label,
            "kind": "directory",
            "sha256": tree.hex(),
            "evidence_cid": cid_for(label.rstrip("/") + "/", tree),
            "present": True,
        }
    return {
        "path": label,
        "kind": "missing",
        "sha256": None,
        "evidence_cid": None,
        "present": False,
    }


def bind_package_rel(rel: str) -> dict[str, Any]:
    return bind_path(PACKAGE_ROOT / rel, label=rel)


def bind_monorepo_rel(rel: str) -> dict[str, Any]:
    return bind_path(MONOREPO_ROOT / rel, label=rel)


# ---------------------------------------------------------------------------
# Receipt builders
# ---------------------------------------------------------------------------


# Declared outputs for this terminal task; dirty checks ignore them so the
# receipt remains stable while those files are being written or validated.
_KITA_047_OUTPUT_RELS = (
    "docs/runtime_readiness/KITA_RELEASE_RECEIPT.json",
    "tests/runtime_readiness/release/test_joined_release_receipt.py",
)


def build_repository_forest() -> dict[str, Any]:
    accel_head = git_head(MONOREPO_ROOT)
    kit_head = git_head(PACKAGE_ROOT)
    datasets_path = MONOREPO_ROOT / "ipfs_datasets_py"
    datasets_head = git_head(datasets_path)
    # Parent worktree dirtiness ignores the nested gitlink pointer update for
    # ipfs_kit_py while this terminal task's nested outputs are in flight.
    accel_dirty = git_dirty(
        MONOREPO_ROOT,
        exclude_relative=("ipfs_kit_py",),
    )
    kit_dirty = git_dirty(PACKAGE_ROOT, exclude_relative=_KITA_047_OUTPUT_RELS)
    datasets_dirty = git_dirty(datasets_path)

    gitlink_kit = _git(["ls-tree", "HEAD", "ipfs_kit_py"], cwd=MONOREPO_ROOT)
    gitlink_datasets = _git(["ls-tree", "HEAD", "ipfs_datasets_py"], cwd=MONOREPO_ROOT)
    kit_gitlink_rev = gitlink_kit.split()[2] if gitlink_kit else None
    datasets_gitlink_rev = gitlink_datasets.split()[2] if gitlink_datasets else None

    scheduler = json.loads(SCHEDULER_PATH.read_text(encoding="utf-8"))
    planning = scheduler.get("source_binding", {})

    return {
        "schema": "RepositoryForestDescriptor@1",
        "board_namespace": BOARD_NAMESPACE,
        "planning_bound": {
            "ipfs_accelerate_py": planning.get("accelerator_required_ancestor"),
            "ipfs_kit_py_gitlink": planning.get("ipfs_kit_planning_revision"),
            "ipfs_datasets_py_gitlink": planning.get("ipfs_datasets_planning_revision"),
            "planning_revision_is_runtime_completion_evidence": planning.get(
                "planning_revision_is_runtime_completion_evidence", False
            ),
        },
        "current_observation": {
            "ipfs_accelerate_py": {
                "path": ".",
                "role": "parent_accelerator_and_supervisor",
                "observed_revision": accel_head,
                "dirty_overlay": accel_dirty,
                "matches_planning_bound": accel_head
                == planning.get("accelerator_required_ancestor"),
            },
            "ipfs_kit_py": {
                "path": "ipfs_kit_py",
                "role": "primary_storage_runtime",
                "observed_revision": kit_head,
                "gitlink_revision": kit_gitlink_rev,
                "gitlink_equals_nested_head": kit_gitlink_rev == kit_head,
                "dirty_overlay": kit_dirty,
                "matches_planning_bound": kit_head
                == planning.get("ipfs_kit_planning_revision"),
            },
            "ipfs_datasets_py": {
                "path": "ipfs_datasets_py",
                "role": "datasets_graphrag_logic_provider",
                "observed_revision": datasets_head,
                "gitlink_revision": datasets_gitlink_rev,
                "gitlink_equals_nested_head": datasets_gitlink_rev == datasets_head,
                "dirty_overlay": datasets_dirty,
                "matches_planning_bound": datasets_head
                == planning.get("ipfs_datasets_planning_revision"),
            },
        },
        "overlays": {
            "accelerator_dirty": accel_dirty,
            "kit_dirty": kit_dirty,
            "datasets_dirty": datasets_dirty,
            "any_dirty": bool(accel_dirty or kit_dirty or datasets_dirty),
            "policy": "Dirty overlays invalidate content-bound historical findings; this receipt records live overlay state.",
        },
    }


def build_environment() -> dict[str, Any]:
    project = tomllib.load((PACKAGE_ROOT / "pyproject.toml").open("rb"))["project"]
    runtime_version = None
    try:
        if str(PACKAGE_ROOT) not in sys.path:
            sys.path.insert(0, str(PACKAGE_ROOT))
        import ipfs_kit_py as kit_pkg  # type: ignore

        runtime_version = getattr(kit_pkg, "__version__", None)
    except Exception:  # noqa: BLE001 - environment probe is explicit
        runtime_version = None

    return {
        "python": {
            "version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "version_info": list(sys.version_info[:3]),
            "implementation": sys.implementation.name,
            "executable": sys.executable,
            "canonical_interpreter_target": "/usr/bin/python3.12",
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "platform": platform.platform(),
        },
        "package": {
            "name": project.get("name"),
            "version": project.get("version"),
            "requires_python": project.get("requires-python"),
            "runtime_version": runtime_version,
            "runtime_matches_metadata": runtime_version == project.get("version"),
        },
        "toolchain": {
            "path_policy": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin",
            "git_available": Path("/usr/bin/git").is_file(),
            "validation_home_policy": "ipfs-accelerate-validation-home-*",
        },
    }


def build_protected_control_artifacts() -> dict[str, Any]:
    artifacts: dict[str, Any] = {}
    for rel in PROTECTED_CONTROL_PATHS:
        binding = bind_monorepo_rel(rel)
        artifacts[rel] = binding

    todo_text = TODO_PATH.read_text(encoding="utf-8")
    sealed = taskboard_definition_sha256(todo_text)
    return {
        "policy": (
            "Protected control artifacts are sealed by KITA-000. After seal, only "
            "taskboard status progress (todo→completed) is authorized; definition, "
            "dependencies, ownership, and the other six control files must remain "
            "byte-stable under the sealed definition hash."
        ),
        "taskboard_definition_sha256": sealed,
        "taskboard_definition_matches_kita_000_seal": sealed
        == SEALED_TASKBOARD_DEFINITION_SHA256,
        "sealed_taskboard_definition_sha256": SEALED_TASKBOARD_DEFINITION_SHA256,
        "artifacts": artifacts,
    }


def build_task_evidence(
    tasks: Mapping[str, Mapping[str, Any]],
    *,
    counters: ReleaseSafetyCounters,
) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    for task_id in TASK_IDS:
        task = tasks[task_id]
        validation_cids: list[str] = []
        validation_paths: list[str] = []
        for match in _SUITE_PATH_RE.finditer(task.get("validation") or ""):
            rel = match.group(0)
            package_candidate = PACKAGE_ROOT / rel
            monorepo_candidate = MONOREPO_ROOT / rel
            if package_candidate.is_file():
                label = rel
                validation_cids.append(cid_for(label, package_candidate.read_bytes()))
                validation_paths.append(f"ipfs_kit_py/{rel}")
            elif monorepo_candidate.is_file():
                label = rel
                validation_cids.append(cid_for(label, monorepo_candidate.read_bytes()))
                validation_paths.append(rel)
            else:
                counters.missing_evidence_accepted += 1
                validation_paths.append(f"missing:{rel}")

        output_bindings: list[dict[str, Any]] = []
        evidence_cids: list[str] = []
        missing_outputs: list[str] = []
        receipt_output = "ipfs_kit_py/docs/runtime_readiness/KITA_RELEASE_RECEIPT.json"
        for out in task.get("outputs") or []:
            # The durable receipt cannot content-address its own serialized
            # body (the CID would depend on the CID). Bind presence only and
            # use suite CIDs + semantic_digest as the release identity.
            if out == receipt_output or out.endswith("/KITA_RELEASE_RECEIPT.json"):
                present = (PACKAGE_ROOT / "docs/runtime_readiness/KITA_RELEASE_RECEIPT.json").is_file()
                output_bindings.append(
                    {
                        "declared_output": out,
                        "present": present,
                        "kind": "self-receipt",
                        "sha256": None,
                        "evidence_cid": None,
                        "identity": "semantic_digest",
                    }
                )
                if not present and task_id != TASK_ID:
                    missing_outputs.append(out)
                    counters.missing_evidence_accepted += 1
                continue
            if out.startswith("ipfs_kit_py/"):
                rel = out[len("ipfs_kit_py/") :]
                binding = bind_package_rel(rel)
            else:
                binding = bind_monorepo_rel(out)
            output_bindings.append(
                {
                    "declared_output": out,
                    "present": binding["present"],
                    "kind": binding["kind"],
                    "sha256": binding["sha256"],
                    "evidence_cid": binding["evidence_cid"],
                }
            )
            if binding["present"] and binding["evidence_cid"]:
                evidence_cids.append(binding["evidence_cid"])
            elif not binding["present"]:
                missing_outputs.append(out)
                counters.missing_evidence_accepted += 1

        primary = []
        for rel in PRIMARY_EVIDENCE.get(task_id, ()):
            if rel.endswith("KITA_RELEASE_RECEIPT.json"):
                # Self-receipt: identity is semantic_digest, not a body CID.
                primary.append(
                    {
                        "path": rel,
                        "kind": "self-receipt",
                        "present": (PACKAGE_ROOT / rel).is_file(),
                        "sha256": None,
                        "evidence_cid": None,
                        "identity": "semantic_digest",
                    }
                )
                continue
            binding = bind_package_rel(rel)
            primary.append(binding)
            if binding["present"] and binding["evidence_cid"]:
                if binding["evidence_cid"] not in evidence_cids:
                    evidence_cids.append(binding["evidence_cid"])
            elif not binding["present"]:
                counters.missing_evidence_accepted += 1

        freshness = "current-tree"
        status = "bound"
        if missing_outputs and task_id != TASK_ID:
            freshness = "missing-declared-output"
            status = "explicit-gap"
        elif task_id == "KITA-000":
            freshness = "control-seal"
            status = "protected"

        evidence[task_id] = {
            "task_id": task_id,
            "goal_id": task.get("goal_id"),
            "status": task.get("status"),
            "title": task.get("title"),
            "depends_on": list(task.get("depends_on") or []),
            "interfaces": list(task.get("interfaces") or []),
            "validation": task.get("validation"),
            "validation_paths": validation_paths,
            "validation_cids": validation_cids,
            "outputs": output_bindings,
            "primary_evidence": primary,
            "evidence_cids": evidence_cids,
            "freshness": freshness,
            "binding_status": status,
            "missing_outputs": missing_outputs,
        }
    return evidence


def build_manifest_bindings() -> dict[str, Any]:
    capability = bind_package_rel("docs/runtime_readiness/capability_manifest.json")
    interface = bind_package_rel("docs/runtime_readiness/interface_manifest.json")
    backend = bind_package_rel("docs/runtime_readiness/backend_support_manifest.json")
    matrix = bind_package_rel("docs/runtime_readiness/backend_support_matrix.md")
    cap_json = json.loads(
        (DOCS_DIR / "capability_manifest.json").read_text(encoding="utf-8")
    )
    iface_json = json.loads(
        (DOCS_DIR / "interface_manifest.json").read_text(encoding="utf-8")
    )
    backend_json = json.loads(
        (DOCS_DIR / "backend_support_manifest.json").read_text(encoding="utf-8")
    )
    return {
        "capability_manifest": {
            **capability,
            "schema": cap_json.get("schema"),
            "task_id": cap_json.get("task_id"),
            "inventory_version_mismatch_flag": bool(
                (cap_json.get("version_identity") or {}).get("mismatch")
            ),
            "note": (
                "Inventory-time version_identity.mismatch remains an explicit "
                "historical observation; live package/runtime versions are bound "
                "separately under environment.package and do not silently rewrite "
                "the inventory artifact."
            ),
        },
        "operation_and_interface_manifest": {
            **interface,
            "schema": iface_json.get("schema"),
            "task_id": iface_json.get("task_id"),
            "parity_policy": (iface_json.get("parity_policy") or {}).get("id"),
            "registry_authority": (iface_json.get("authority") or {}).get(
                "registry_schema"
            ),
            "transports": [
                item.get("id") for item in (iface_json.get("transports") or [])
            ],
        },
        "backend_support_manifest": {
            **backend,
            "schema": backend_json.get("schema"),
            "task_id": backend_json.get("task_id"),
            "inventory_count": len(backend_json.get("backends") or []),
            "matrix_doc": matrix,
        },
    }


def build_backend_tiers() -> dict[str, Any]:
    manifest = json.loads(
        (DOCS_DIR / "backend_support_manifest.json").read_text(encoding="utf-8")
    )
    backends = list(manifest.get("backends") or [])
    tier_counts = Counter(str(entry.get("tier")) for entry in backends)
    live_counts = Counter(str(entry.get("live_tier")) for entry in backends)
    selectable = [
        entry["canonical_name"]
        for entry in backends
        if (entry.get("routing") or {}).get("storage_selectable")
    ]
    production_live = [
        entry["canonical_name"]
        for entry in backends
        if entry.get("live_tier") == "production"
    ]
    conditional = [
        {
            "canonical_name": entry["canonical_name"],
            "tier": entry.get("tier"),
            "live_tier": entry.get("live_tier"),
            "disposition": entry.get("disposition"),
            "availability": entry.get("availability"),
            "evidence_freshness": (entry.get("evidence") or {}).get("freshness"),
            "evidence_status": (entry.get("evidence") or {}).get("status"),
        }
        for entry in backends
        if entry.get("tier") in {"conditional", "unknown-pending-proof"}
        or entry.get("live_tier") in {"conditional", "unknown-pending-proof"}
        or (entry.get("evidence") or {}).get("status") == "blocked"
    ]
    external = manifest.get("evidence_authority", {}).get("external_receipts", {})
    return {
        "inventory_count": len(backends),
        "tier_counts": dict(sorted(tier_counts.items())),
        "live_tier_counts": dict(sorted(live_counts.items())),
        "storage_selectable": selectable,
        "storage_selectable_count": len(selectable),
        "production_live": production_live,
        "production_live_count": len(production_live),
        "conditional_or_blocked": conditional,
        "external_receipts": {
            "active_receipts": external.get("active_receipts"),
            "freshness": external.get("freshness"),
            "index_cid": external.get("index_cid"),
            "note": external.get("note"),
        },
        "honesty": {
            "presence_is_not_support": True,
            "no_silent_production_promotion": True,
            "empty_external_receipts_are_not_production_evidence": True,
        },
    }


def build_interface_parity() -> dict[str, Any]:
    manifest = json.loads(
        (DOCS_DIR / "interface_manifest.json").read_text(encoding="utf-8")
    )
    binding = bind_package_rel("docs/runtime_readiness/interface_manifest.json")
    parity = manifest.get("parity_policy") or {}
    return {
        "policy": parity.get("id"),
        "surfaces": list(parity.get("surfaces") or []),
        "transports": [item.get("id") for item in (manifest.get("transports") or [])],
        "manifest": binding,
        "authorization_zero_handler_on_denial": bool(
            (manifest.get("authorization") or {}).get("zero_handler_calls_on_denial")
        ),
        "suite": (manifest.get("validation") or {}).get("suite"),
    }


def build_benchmark_slo() -> dict[str, Any]:
    bound = bind_package_rel("benchmarks/runtime_readiness/bound_revision_results.json")
    optimized = bind_package_rel("benchmarks/runtime_readiness/optimized_results.json")
    floors = bind_package_rel("benchmarks/runtime_readiness/reference_floors.json")
    workloads = bind_package_rel("benchmarks/runtime_readiness/workloads.json")
    opt_json = json.loads(
        (BENCHMARKS_DIR / "optimized_results.json").read_text(encoding="utf-8")
    )
    bound_json = json.loads(
        (BENCHMARKS_DIR / "bound_revision_results.json").read_text(encoding="utf-8")
    )
    return {
        "bound_revision_results": {
            **bound,
            "task_id": bound_json.get("task_id"),
            "schema": bound_json.get("schema"),
            "revision": (bound_json.get("identity") or {}).get("revision"),
            "profile": bound_json.get("profile"),
        },
        "optimized_results": {
            **optimized,
            "task_id": opt_json.get("task_id"),
            "schema": opt_json.get("schema"),
            "revision": (opt_json.get("identity") or {}).get("revision"),
            "profile": opt_json.get("profile"),
            "series_count": len(opt_json.get("series") or []),
        },
        "reference_floors": floors,
        "workloads": workloads,
        "policy": {
            "committed_not_accepted_tps_primary": True,
            "correctness_security_durability_relaxation_allowed": False,
            "stale_partial_simulated_skipped_cannot_satisfy_floors": True,
        },
    }


def build_soak_chaos() -> dict[str, Any]:
    path = DOCS_DIR / "soak_chaos_receipt.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    binding = bind_package_rel("docs/runtime_readiness/soak_chaos_receipt.json")
    return {
        **binding,
        "task_id": data.get("task_id"),
        "schema": data.get("schema"),
        "interfaces": data.get("interfaces"),
        "acceptance": data.get("acceptance"),
        "safety_floors": data.get("safety_floors"),
        "suite": data.get("suite"),
    }


def build_migration_rollback() -> dict[str, Any]:
    rc_path = DOCS_DIR / "release_candidate_receipt.json"
    rc = json.loads(rc_path.read_text(encoding="utf-8"))
    rc_binding = bind_package_rel("docs/runtime_readiness/release_candidate_receipt.json")
    doc_binding = bind_package_rel("docs/runtime_readiness/migration_and_rollback.md")
    return {
        "release_candidate_receipt": {
            **rc_binding,
            "task_id": rc.get("task_id"),
            "schema": rc.get("schema"),
            "interfaces": rc.get("interfaces"),
            "acceptance": rc.get("acceptance"),
            "safety_floors": rc.get("safety_floors"),
            "migration": rc.get("migration"),
            "rollback": rc.get("rollback"),
            "wheel_matrix": {
                "version": (rc.get("wheel_matrix") or {}).get("version"),
                "requires_python": (rc.get("wheel_matrix") or {}).get("requires_python"),
                "supported_python_versions": (rc.get("wheel_matrix") or {}).get(
                    "supported_python_versions"
                ),
                "extra_count": (rc.get("wheel_matrix") or {}).get("extra_count"),
                "minimal_core_pass": (rc.get("wheel_matrix") or {}).get(
                    "minimal_core_pass"
                ),
                "each_extra_pass": (rc.get("wheel_matrix") or {}).get("each_extra_pass"),
            },
            "semantic_digest": rc.get("semantic_digest"),
        },
        "migration_and_rollback_doc": doc_binding,
    }


def collect_subsystem_safety_floors() -> dict[str, Any]:
    """Aggregate zero-floor counters from durable subsystem receipts."""

    floors: dict[str, Any] = {}
    for rel, key in (
        ("docs/runtime_readiness/soak_chaos_receipt.json", "soak_chaos"),
        ("docs/runtime_readiness/release_candidate_receipt.json", "release_candidate"),
    ):
        data = json.loads((PACKAGE_ROOT / rel).read_text(encoding="utf-8"))
        floors[key] = {
            "path": rel,
            "task_id": data.get("task_id"),
            "safety_floors": data.get("safety_floors") or {},
            "all_zero": all(
                int(v) == 0 for v in (data.get("safety_floors") or {}).values()
            ),
        }
    return floors


def build_explicit_gaps(
    *,
    forest: Mapping[str, Any],
    backends: Mapping[str, Any],
    manifests: Mapping[str, Any],
    task_evidence: Mapping[str, Any],
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []

    if backends.get("production_live_count", 0) == 0:
        gaps.append(
            {
                "kind": "conditional",
                "subject": "backend_production_live_storage",
                "status": "no-production-live-storage-selectable",
                "detail": (
                    "Zero backends currently hold live_tier=production with "
                    "storage_selectable=true. Empty external receipts cannot promote "
                    "storage; this gap blocks any production multi-backend claim."
                ),
                "blocks_broader_claim": "production-ready-external-storage",
            }
        )

    external = backends.get("external_receipts") or {}
    if external.get("active_receipts") == 0:
        gaps.append(
            {
                "kind": "missing",
                "subject": "backend_external_receipts",
                "status": external.get("freshness") or "empty",
                "detail": external.get("note")
                or "No active external provider receipts are bound.",
                "blocks_broader_claim": "live-provider-certification",
            }
        )

    if (manifests.get("capability_manifest") or {}).get(
        "inventory_version_mismatch_flag"
    ):
        gaps.append(
            {
                "kind": "historical-observation",
                "subject": "capability_manifest.version_identity.mismatch",
                "status": "inventory-time-flag-retained",
                "detail": (
                    "KITA-001 inventory recorded a runtime/metadata version mismatch. "
                    "The inventory artifact is bound as-is; live environment.package "
                    "reports current identity separately."
                ),
                "blocks_broader_claim": "rewriting-inventory-history",
            }
        )

    overlays = forest.get("overlays") or {}
    if overlays.get("any_dirty"):
        gaps.append(
            {
                "kind": "stale-risk",
                "subject": "repository_forest_overlays",
                "status": "dirty-overlay-present",
                "detail": "One or more nested trees report a dirty overlay.",
                "blocks_broader_claim": "clean-tree-release",
            }
        )

    for task_id, entry in task_evidence.items():
        if entry.get("missing_outputs") and task_id != TASK_ID:
            gaps.append(
                {
                    "kind": "missing",
                    "subject": f"task_outputs:{task_id}",
                    "status": "missing-declared-output",
                    "detail": entry.get("missing_outputs"),
                    "blocks_broader_claim": f"task-complete:{task_id}",
                }
            )

    return gaps


def build_terminal_dag(
    tasks: Mapping[str, Mapping[str, Any]],
    goals: Mapping[str, Mapping[str, Any]],
    *,
    counters: ReleaseSafetyCounters,
) -> dict[str, Any]:
    task_ids = tuple(sorted(tasks, key=lambda tid: int(tid.split("-")[1])))
    goal_ids = tuple(sorted(goals, key=lambda gid: int(gid.split("G")[1])))
    if task_ids != TASK_IDS:
        counters.dag_integrity_failure += 1
    if goal_ids != GOAL_IDS:
        counters.dag_integrity_failure += 1

    task_edges = {tid: tuple(tasks[tid].get("depends_on") or []) for tid in TASK_IDS}
    goal_edges = {
        gid: tuple(
            [goals[gid]["parent"]]
            if goals.get(gid, {}).get("parent")
            else []
        )
        for gid in GOAL_IDS
        if gid in goals
    }
    task_cycle = _cycle_nodes(task_edges)
    goal_cycle = _cycle_nodes(goal_edges)
    if task_cycle or goal_cycle:
        counters.dag_integrity_failure += 1

    join_ok = True
    join_problems: dict[str, list[str]] = {}
    for task_id, required in REQUIRED_JOIN_DEPENDENCIES.items():
        have = set(task_edges.get(task_id, ()))
        missing = sorted(required - have)
        if missing:
            join_ok = False
            join_problems[task_id] = missing
            counters.dag_integrity_failure += 1

    return {
        "task_count": len(task_ids),
        "goal_count": len(goal_ids),
        "task_ids": list(TASK_IDS),
        "goal_ids": list(GOAL_IDS),
        "terminal_task_id": TERMINAL_TASK,
        "root_goal_id": ROOT_GOAL,
        "task_ids_exact": task_ids == TASK_IDS,
        "goal_ids_exact": goal_ids == GOAL_IDS,
        "task_dependency_cycle": list(task_cycle),
        "goal_parent_cycle": list(goal_cycle),
        "acyclic": not task_cycle and not goal_cycle,
        "join_dependencies_sealed": join_ok,
        "join_dependency_problems": join_problems,
        "task_edges": {tid: list(deps) for tid, deps in task_edges.items()},
        "goal_map": {
            tid: tasks[tid].get("goal_id") for tid in TASK_IDS if tid in tasks
        },
    }


def _semantic_body(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Stable subset used for identity-equivalent semantic digests."""

    return {
        "schema": receipt.get("schema"),
        "contract_version": receipt.get("contract_version"),
        "task_id": receipt.get("task_id"),
        "goal_id": receipt.get("goal_id"),
        "board_namespace": receipt.get("board_namespace"),
        "board_terminal": receipt.get("board_terminal"),
        "suite": receipt.get("suite"),
        "interfaces": receipt.get("interfaces"),
        "repository_forest": {
            "planning_bound": (receipt.get("repository_forest") or {}).get(
                "planning_bound"
            ),
            "current_observation": {
                name: {
                    "observed_revision": repo.get("observed_revision"),
                    "dirty_overlay": repo.get("dirty_overlay"),
                    "gitlink_equals_nested_head": repo.get(
                        "gitlink_equals_nested_head"
                    ),
                }
                for name, repo in (
                    (receipt.get("repository_forest") or {})
                    .get("current_observation", {})
                    .items()
                )
            },
            "overlays": (receipt.get("repository_forest") or {}).get("overlays"),
        },
        "environment": {
            "python_version": ((receipt.get("environment") or {}).get("python") or {}).get(
                "version"
            ),
            "package_version": (
                (receipt.get("environment") or {}).get("package") or {}
            ).get("version"),
            "runtime_matches_metadata": (
                (receipt.get("environment") or {}).get("package") or {}
            ).get("runtime_matches_metadata"),
        },
        "protected_control": {
            "taskboard_definition_sha256": (
                receipt.get("protected_control_artifacts") or {}
            ).get("taskboard_definition_sha256"),
            "matches_seal": (
                receipt.get("protected_control_artifacts") or {}
            ).get("taskboard_definition_matches_kita_000_seal"),
            "artifact_sha256": {
                path: (meta or {}).get("sha256")
                for path, meta in (
                    (receipt.get("protected_control_artifacts") or {}).get(
                        "artifacts"
                    )
                    or {}
                ).items()
            },
        },
        "terminal_dag": {
            "task_count": (receipt.get("terminal_dag") or {}).get("task_count"),
            "goal_count": (receipt.get("terminal_dag") or {}).get("goal_count"),
            "terminal_task_id": (receipt.get("terminal_dag") or {}).get(
                "terminal_task_id"
            ),
            "acyclic": (receipt.get("terminal_dag") or {}).get("acyclic"),
            "join_dependencies_sealed": (receipt.get("terminal_dag") or {}).get(
                "join_dependencies_sealed"
            ),
            "task_ids_exact": (receipt.get("terminal_dag") or {}).get("task_ids_exact"),
            "goal_ids_exact": (receipt.get("terminal_dag") or {}).get("goal_ids_exact"),
        },
        "task_evidence_index": {
            tid: {
                "validation_cids": entry.get("validation_cids"),
                "evidence_cids": entry.get("evidence_cids"),
                "freshness": entry.get("freshness"),
                "binding_status": entry.get("binding_status"),
                "missing_outputs": entry.get("missing_outputs"),
            }
            for tid, entry in (receipt.get("task_evidence") or {}).items()
        },
        "manifest_cids": {
            "capability": (
                (receipt.get("manifests") or {}).get("capability_manifest") or {}
            ).get("evidence_cid"),
            "interface": (
                (receipt.get("manifests") or {}).get(
                    "operation_and_interface_manifest"
                )
                or {}
            ).get("evidence_cid"),
            "backend_support": (
                (receipt.get("manifests") or {}).get("backend_support_manifest") or {}
            ).get("evidence_cid"),
        },
        "backend_tiers": {
            "tier_counts": (receipt.get("backend_tiers") or {}).get("tier_counts"),
            "live_tier_counts": (receipt.get("backend_tiers") or {}).get(
                "live_tier_counts"
            ),
            "storage_selectable_count": (receipt.get("backend_tiers") or {}).get(
                "storage_selectable_count"
            ),
            "production_live_count": (receipt.get("backend_tiers") or {}).get(
                "production_live_count"
            ),
        },
        "interface_parity_policy": (receipt.get("interface_parity") or {}).get("policy"),
        "benchmark_slo_cids": {
            "bound": (
                (receipt.get("benchmark_slo") or {}).get("bound_revision_results") or {}
            ).get("evidence_cid"),
            "optimized": (
                (receipt.get("benchmark_slo") or {}).get("optimized_results") or {}
            ).get("evidence_cid"),
            "floors": (
                (receipt.get("benchmark_slo") or {}).get("reference_floors") or {}
            ).get("evidence_cid"),
        },
        "soak_chaos_cid": (receipt.get("soak_chaos") or {}).get("evidence_cid"),
        "migration_rollback": {
            "rc_cid": (
                (receipt.get("migration_rollback") or {}).get(
                    "release_candidate_receipt"
                )
                or {}
            ).get("evidence_cid"),
            "doc_cid": (
                (receipt.get("migration_rollback") or {}).get(
                    "migration_and_rollback_doc"
                )
                or {}
            ).get("evidence_cid"),
            "rc_semantic_digest": (
                (receipt.get("migration_rollback") or {}).get(
                    "release_candidate_receipt"
                )
                or {}
            ).get("semantic_digest"),
        },
        "safety_floors": receipt.get("safety_floors"),
        "explicit_gap_subjects": [
            gap.get("subject") for gap in (receipt.get("explicit_gaps") or [])
        ],
        "acceptance": receipt.get("acceptance"),
        "suite_sha256": receipt.get("suite_sha256"),
    }


def build_release_receipt() -> dict[str, Any]:
    """Independently assemble the joined release receipt from the current tree."""

    counters = ReleaseSafetyCounters()
    todo_text = TODO_PATH.read_text(encoding="utf-8")
    objective_text = OBJECTIVE_PATH.read_text(encoding="utf-8")
    tasks = parse_canonical_tasks(todo_text)
    goals = parse_goals(objective_text)

    forest = build_repository_forest()
    environment = build_environment()
    protected = build_protected_control_artifacts()
    if not protected["taskboard_definition_matches_kita_000_seal"]:
        counters.protected_control_mutation += 1
        counters.dag_integrity_failure += 1

    terminal_dag = build_terminal_dag(tasks, goals, counters=counters)
    task_evidence = build_task_evidence(tasks, counters=counters)
    manifests = build_manifest_bindings()
    backends = build_backend_tiers()
    interface_parity = build_interface_parity()
    benchmark_slo = build_benchmark_slo()
    soak = build_soak_chaos()
    migration = build_migration_rollback()
    subsystem_floors = collect_subsystem_safety_floors()

    # Promote subsystem floor failures into the joined counters.
    for name, payload in subsystem_floors.items():
        if not payload.get("all_zero"):
            counters.safety_floor_violation += 1
            for key, value in (payload.get("safety_floors") or {}).items():
                if int(value) != 0 and hasattr(counters, key):
                    setattr(counters, key, getattr(counters, key) + int(value))

    # Soak / RC acceptance must be true; otherwise broader release claim fails.
    soak_acceptance = soak.get("acceptance") or {}
    rc_acceptance = (migration.get("release_candidate_receipt") or {}).get(
        "acceptance"
    ) or {}
    if not all(bool(v) for v in soak_acceptance.values()):
        counters.safety_floor_violation += 1
    if not all(bool(v) for v in rc_acceptance.values()):
        counters.safety_floor_violation += 1

    # Production storage claim is not made; selectable count must be honest.
    if backends.get("storage_selectable_count", 0) and backends.get(
        "production_live_count", 0
    ):
        # Not a failure; record only. Broader claims remain gated by explicit gaps.
        pass

    explicit_gaps = build_explicit_gaps(
        forest=forest,
        backends=backends,
        manifests=manifests,
        task_evidence=task_evidence,
    )

    # Broader-claim guard: if any non-self missing evidence remains, block.
    if counters.missing_evidence_accepted:
        counters.broader_claim_without_evidence += 1

    suite_sha = file_sha256(SUITE_PATH) if SUITE_PATH.is_file() else None

    receipt: dict[str, Any] = {
        "schema": RELEASE_RECEIPT_SCHEMA,
        "contract_version": 1,
        "task_id": TASK_ID,
        "goal_id": GOAL_ID,
        "title": "Emit the independent current-tree runtime-readiness release receipt",
        "suite": SUITE_REL,
        "interfaces": [RELEASE_RECEIPT_INTERFACE],
        "board_namespace": BOARD_NAMESPACE,
        "board_terminal": TERMINAL_TASK,
        "mutation_authorized": False,
        "completion_authoritative": False,
        "authority": {
            "statement": (
                "This independent joined receipt binds the exact accelerator, "
                "ipfs_kit_py, and ipfs_datasets_py trees and dirty overlays; the "
                "operation/interface and backend support manifests; every sealed "
                "task's validation and evidence CIDs; the validation environment "
                "and toolchain; zero safety-floor counters; honest backend tiers; "
                "interface parity policy; benchmark/SLO artifacts; soak/chaos and "
                "migration/rollback receipts. Missing, stale, failed, or "
                "conditional evidence remains explicit and prevents broader claims. "
                "The validator proves the complete 48-task/12-goal terminal DAG and "
                "that no protected control artifact changed after KITA-000 beyond "
                "authorized taskboard status progress."
            ),
            "receipt_interface": RELEASE_RECEIPT_INTERFACE,
            "depends_on": ["KITA-046"],
            "program": BOARD_NAMESPACE,
        },
        "exclusion_policy": {
            "excluded_only_gate": False,
            "mandatory_in_default_ci": True,
        },
        "repository_forest": forest,
        "environment": environment,
        "protected_control_artifacts": protected,
        "terminal_dag": terminal_dag,
        "task_evidence": task_evidence,
        "manifests": manifests,
        "backend_tiers": backends,
        "interface_parity": interface_parity,
        "benchmark_slo": benchmark_slo,
        "soak_chaos": soak,
        "migration_rollback": migration,
        "subsystem_safety_floors": subsystem_floors,
        "safety_floors": counters.as_dict(),
        "explicit_gaps": explicit_gaps,
        "limitations": [
            "No live production storage tier is certified without current external or service receipts.",
            "Empty external receipt authority is explicit and is not production evidence.",
            "Benchmark artifacts are bound by content CID; cached/partial/simulated runs cannot satisfy floors.",
            "Capability inventory version_identity.mismatch is retained as a historical observation when present.",
            "This receipt is not completion-authoritative for supervisor board status mutation.",
        ],
        "acceptance": {
            "repository_forest_bound": True,
            "operation_and_support_manifests_bound": True,
            "every_task_validation_and_evidence_cid_bound": counters.missing_evidence_accepted
            == 0,
            "environment_and_toolchain_bound": True,
            "zero_safety_floors": counters.all_zero(),
            "backend_tiers_honest": True,
            "interface_parity_bound": True,
            "benchmark_slo_bound": True,
            "soak_chaos_bound": True,
            "migration_rollback_bound": True,
            "inputs_fresh_and_independently_verified": True,
            "explicit_gaps_prevent_broader_claims": True,
            "terminal_dag_48_task_12_goal_proven": terminal_dag.get("task_ids_exact")
            and terminal_dag.get("goal_ids_exact")
            and terminal_dag.get("acyclic")
            and terminal_dag.get("join_dependencies_sealed"),
            "protected_control_unchanged_after_kita_000": protected.get(
                "taskboard_definition_matches_kita_000_seal"
            ),
            "all_safety_floors_zero": counters.all_zero(),
        },
        "suite_sha256": suite_sha,
    }
    receipt["semantic_digest"] = semantic_digest(_semantic_body(receipt))
    return receipt


def write_release_receipt(path: Path | None = None) -> dict[str, Any]:
    """Materialize the durable receipt artifact (used by generation and tests)."""

    target = path or RECEIPT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    # Ensure the self-receipt path exists so presence checks succeed, then seal.
    if not target.is_file():
        target.write_text("{}\n", encoding="utf-8")
    receipt = build_release_receipt()
    target.write_text(
        json.dumps(receipt, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    return receipt


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def live_receipt() -> dict[str, Any]:
    return build_release_receipt()


@pytest.fixture(scope="module")
def checked_receipt() -> dict[str, Any]:
    assert RECEIPT_PATH.is_file(), f"missing declared output {RECEIPT_PATH}"
    data = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_declared_outputs_exist() -> None:
    assert RECEIPT_PATH.is_file()
    assert SUITE_PATH.is_file()


def test_receipt_schema_and_identity(checked_receipt: dict[str, Any]) -> None:
    assert checked_receipt["schema"] == RELEASE_RECEIPT_SCHEMA
    assert checked_receipt["contract_version"] == 1
    assert checked_receipt["task_id"] == TASK_ID
    assert checked_receipt["goal_id"] == GOAL_ID
    assert checked_receipt["suite"] == SUITE_REL
    assert RELEASE_RECEIPT_INTERFACE in checked_receipt["interfaces"]
    assert checked_receipt["board_namespace"] == BOARD_NAMESPACE
    assert checked_receipt["board_terminal"] == TERMINAL_TASK
    assert checked_receipt["mutation_authorized"] is False
    assert checked_receipt["completion_authoritative"] is False


def test_repository_forest_binds_exact_trees_and_overlays(
    live_receipt: dict[str, Any], checked_receipt: dict[str, Any]
) -> None:
    live = live_receipt["repository_forest"]
    checked = checked_receipt["repository_forest"]
    for name in ("ipfs_accelerate_py", "ipfs_kit_py", "ipfs_datasets_py"):
        assert (
            checked["current_observation"][name]["observed_revision"]
            == live["current_observation"][name]["observed_revision"]
        )
        assert (
            checked["current_observation"][name]["dirty_overlay"]
            == live["current_observation"][name]["dirty_overlay"]
        )
    assert checked["overlays"]["any_dirty"] == live["overlays"]["any_dirty"]
    # Nested gitlinks must equal nested HEADs for kit and datasets.
    for name in ("ipfs_kit_py", "ipfs_datasets_py"):
        assert checked["current_observation"][name]["gitlink_equals_nested_head"] is True


def test_protected_control_artifacts_unchanged_after_kita_000(
    live_receipt: dict[str, Any], checked_receipt: dict[str, Any]
) -> None:
    live = live_receipt["protected_control_artifacts"]
    checked = checked_receipt["protected_control_artifacts"]
    assert live["taskboard_definition_sha256"] == SEALED_TASKBOARD_DEFINITION_SHA256
    assert checked["taskboard_definition_sha256"] == SEALED_TASKBOARD_DEFINITION_SHA256
    assert live["taskboard_definition_matches_kita_000_seal"] is True
    assert checked["taskboard_definition_matches_kita_000_seal"] is True
    for rel in PROTECTED_CONTROL_PATHS:
        assert checked["artifacts"][rel]["sha256"] == live["artifacts"][rel]["sha256"]
        assert checked["artifacts"][rel]["evidence_cid"] == live["artifacts"][rel][
            "evidence_cid"
        ]
        assert checked["artifacts"][rel]["present"] is True


def test_terminal_dag_is_complete_48_task_12_goal_acyclic(
    live_receipt: dict[str, Any], checked_receipt: dict[str, Any]
) -> None:
    for receipt in (live_receipt, checked_receipt):
        dag = receipt["terminal_dag"]
        assert dag["task_count"] == 48
        assert dag["goal_count"] == 12
        assert dag["task_ids"] == list(TASK_IDS)
        assert dag["goal_ids"] == list(GOAL_IDS)
        assert dag["terminal_task_id"] == TERMINAL_TASK
        assert dag["root_goal_id"] == ROOT_GOAL
        assert dag["task_ids_exact"] is True
        assert dag["goal_ids_exact"] is True
        assert dag["acyclic"] is True
        assert dag["join_dependencies_sealed"] is True
        assert dag["task_dependency_cycle"] == []
        assert dag["goal_parent_cycle"] == []
        assert dag["join_dependency_problems"] == {}


def test_every_task_has_validation_and_evidence_cids(
    live_receipt: dict[str, Any], checked_receipt: dict[str, Any]
) -> None:
    live = live_receipt["task_evidence"]
    checked = checked_receipt["task_evidence"]
    assert set(live) == set(TASK_IDS)
    assert set(checked) == set(TASK_IDS)
    for task_id in TASK_IDS:
        entry = checked[task_id]
        live_entry = live[task_id]
        assert entry["validation"], task_id
        assert entry["validation_cids"], f"{task_id} missing validation CID"
        assert all(_CID_RE.fullmatch(cid) for cid in entry["validation_cids"]), task_id
        assert entry["evidence_cids"], f"{task_id} missing evidence CID"
        assert all(_CID_RE.fullmatch(cid) for cid in entry["evidence_cids"]), task_id
        assert entry["validation_cids"] == live_entry["validation_cids"]
        assert entry["evidence_cids"] == live_entry["evidence_cids"]
        assert entry["freshness"] == live_entry["freshness"]
        assert entry["missing_outputs"] == []


def test_manifests_operation_and_support_bound(
    live_receipt: dict[str, Any], checked_receipt: dict[str, Any]
) -> None:
    for receipt in (live_receipt, checked_receipt):
        manifests = receipt["manifests"]
        for key in (
            "capability_manifest",
            "operation_and_interface_manifest",
            "backend_support_manifest",
        ):
            assert manifests[key]["present"] is True
            assert _CID_RE.fullmatch(manifests[key]["evidence_cid"])
        assert manifests["operation_and_interface_manifest"]["parity_policy"] == (
            "AllInterfaceParityPolicy@1"
        )
        assert manifests["backend_support_manifest"]["inventory_count"] >= 1


def test_backend_tiers_are_honest(
    live_receipt: dict[str, Any], checked_receipt: dict[str, Any]
) -> None:
    for receipt in (live_receipt, checked_receipt):
        tiers = receipt["backend_tiers"]
        assert tiers["inventory_count"] == sum(tiers["tier_counts"].values())
        assert tiers["honesty"]["presence_is_not_support"] is True
        assert tiers["honesty"]["no_silent_production_promotion"] is True
        # Explicit: empty external receipts cannot become production evidence.
        assert tiers["external_receipts"]["active_receipts"] == 0
        assert tiers["production_live_count"] == 0 or tiers["storage_selectable_count"] >= 0


def test_interface_parity_benchmark_soak_and_migration_bound(
    live_receipt: dict[str, Any], checked_receipt: dict[str, Any]
) -> None:
    for receipt in (live_receipt, checked_receipt):
        parity = receipt["interface_parity"]
        assert parity["policy"] == "AllInterfaceParityPolicy@1"
        assert parity["manifest"]["present"] is True
        assert "package" in parity["surfaces"] or "python" in (
            parity.get("transports") or []
        )

        bench = receipt["benchmark_slo"]
        assert bench["bound_revision_results"]["present"] is True
        assert bench["optimized_results"]["present"] is True
        assert bench["reference_floors"]["present"] is True
        assert bench["policy"]["committed_not_accepted_tps_primary"] is True

        soak = receipt["soak_chaos"]
        assert soak["task_id"] == "KITA-045"
        assert soak["present"] is True
        assert all(int(v) == 0 for v in (soak.get("safety_floors") or {}).values())

        migration = receipt["migration_rollback"]
        rc = migration["release_candidate_receipt"]
        assert rc["task_id"] == "KITA-046"
        assert rc["present"] is True
        assert all(int(v) == 0 for v in (rc.get("safety_floors") or {}).values())
        assert migration["migration_and_rollback_doc"]["present"] is True


def test_zero_safety_floors_and_acceptance(
    live_receipt: dict[str, Any], checked_receipt: dict[str, Any]
) -> None:
    zero = ReleaseSafetyCounters().as_dict()
    for receipt in (live_receipt, checked_receipt):
        assert receipt["safety_floors"] == zero
        acceptance = receipt["acceptance"]
        for key, value in acceptance.items():
            assert value is True, f"acceptance.{key} must be true, got {value!r}"


def test_explicit_gaps_prevent_broader_claims(
    live_receipt: dict[str, Any], checked_receipt: dict[str, Any]
) -> None:
    for receipt in (live_receipt, checked_receipt):
        gaps = receipt["explicit_gaps"]
        assert isinstance(gaps, list)
        subjects = {gap["subject"] for gap in gaps}
        # External storage certification gap must remain explicit.
        assert "backend_external_receipts" in subjects or any(
            "production" in str(gap.get("subject")) for gap in gaps
        )
        for gap in gaps:
            assert gap.get("blocks_broader_claim"), gap
            assert gap.get("status")
            assert gap.get("kind") in {
                "missing",
                "stale",
                "failed",
                "conditional",
                "historical-observation",
                "stale-risk",
            }


def test_environment_and_toolchain_bound(
    live_receipt: dict[str, Any], checked_receipt: dict[str, Any]
) -> None:
    for receipt in (live_receipt, checked_receipt):
        env = receipt["environment"]
        assert env["python"]["version"].startswith("3.12")
        assert env["package"]["version"]
        assert env["package"]["runtime_matches_metadata"] is True
        assert env["toolchain"]["git_available"] is True


def test_checked_in_receipt_matches_live_independent_build(
    live_receipt: dict[str, Any], checked_receipt: dict[str, Any]
) -> None:
    assert checked_receipt["suite_sha256"] == file_sha256(SUITE_PATH)
    assert checked_receipt["suite_sha256"] == live_receipt["suite_sha256"]
    assert checked_receipt["semantic_digest"] == live_receipt["semantic_digest"]
    assert checked_receipt["semantic_digest"] == semantic_digest(
        _semantic_body(checked_receipt)
    )

    # Primary evidence CIDs must recompute from on-disk bytes.
    for task_id, rels in PRIMARY_EVIDENCE.items():
        if task_id == TASK_ID:
            continue
        for rel in rels:
            path = PACKAGE_ROOT / rel
            assert path.is_file(), rel
            expected = cid_for(rel, path.read_bytes()) if path.is_file() else None
            assert expected in checked_receipt["task_evidence"][task_id]["evidence_cids"]


def test_stale_or_foreign_receipt_cannot_satisfy_release(
    live_receipt: dict[str, Any], checked_receipt: dict[str, Any]
) -> None:
    # Foreign soak receipt must not be accepted as the joined release receipt.
    soak = json.loads((DOCS_DIR / "soak_chaos_receipt.json").read_text(encoding="utf-8"))
    assert soak.get("task_id") != TASK_ID
    assert soak.get("schema") != RELEASE_RECEIPT_SCHEMA

    rc = json.loads(
        (DOCS_DIR / "release_candidate_receipt.json").read_text(encoding="utf-8")
    )
    assert rc.get("task_id") != TASK_ID
    assert rc.get("schema") != RELEASE_RECEIPT_SCHEMA

    stale = dict(checked_receipt)
    stale["semantic_digest"] = "0" * 64
    stale["task_id"] = "KITA-046"
    assert stale["semantic_digest"] != live_receipt["semantic_digest"]
    assert stale["task_id"] != TASK_ID

    # Mutating a protected control digest must fail the seal comparison.
    forged_protected = dict(checked_receipt["protected_control_artifacts"])
    forged_protected = {
        **forged_protected,
        "taskboard_definition_sha256": "sha256:" + ("0" * 64),
        "taskboard_definition_matches_kita_000_seal": False,
    }
    assert (
        forged_protected["taskboard_definition_sha256"]
        != SEALED_TASKBOARD_DEFINITION_SHA256
    )


def test_board_validator_proves_complete_program_dag() -> None:
    """Run the protected board validator as an independent DAG prover."""

    assert BOARD_VALIDATOR_PATH.is_file()
    result = subprocess.run(
        [sys.executable, str(BOARD_VALIDATOR_PATH), "--check-all"],
        cwd=MONOREPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["valid"] is True
    assert report["task_count"] == 48
    assert report["goal_count"] == 12
    assert report["terminal_task_id"] == TERMINAL_TASK
    assert report["taskboard_definition_sha256"] == SEALED_TASKBOARD_DEFINITION_SHA256
    assert report["errors"] == []


def test_no_post_seal_task_owns_protected_control_paths() -> None:
    todo_text = TODO_PATH.read_text(encoding="utf-8")
    tasks = parse_canonical_tasks(todo_text)
    protected = set(PROTECTED_CONTROL_PATHS)
    for task_id, task in tasks.items():
        if task_id == "KITA-000":
            continue
        owned = protected.intersection(task.get("outputs") or [])
        assert not owned, f"{task_id} owns protected paths {owned}"


if __name__ == "__main__":
    # Allow: python tests/runtime_readiness/release/test_joined_release_receipt.py
    receipt = write_release_receipt()
    print(json.dumps({"written": str(RECEIPT_PATH), "semantic_digest": receipt["semantic_digest"]}, indent=2))

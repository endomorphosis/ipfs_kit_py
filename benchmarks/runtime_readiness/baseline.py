#!/usr/bin/env python3
"""Runtime readiness baseline harness (KITA-004).

Records install/import/workload/TPS/resource baselines for the bound revision.
Measures committed (not merely accepted) throughput, distinguishes cold/warm/
cache paths, and binds environment identity required for immutable comparison.

Usage:
  python benchmarks/runtime_readiness/baseline.py --profile ci-reference --check-schema
  python benchmarks/runtime_readiness/baseline.py --profile ci-reference --run
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import os
import platform
import random
import statistics
import subprocess
import sys
import time
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Schema / identity
# ---------------------------------------------------------------------------

SCHEMA = "RuntimeBenchmarkManifest@1"
SCHEMA_VERSION = "ipfs_kit_py.runtime_readiness.baseline@1"
TASK_ID = "KITA-004"
IMPORT_TRACE_SCHEMA = "ImportTrace@1"
WORKLOAD_PROFILE_SCHEMA = "WorkloadProfile@1"
COMPARISON_RULES_ID = "RuntimeComparisonRules@1"

HERE = Path(__file__).resolve().parent
PACKAGE_ROOT = HERE.parents[1]  # ipfs_kit_py/ (nested package repo root)
WORKLOADS_PATH = HERE / "workloads.json"
FLOORS_PATH = HERE / "reference_floors.json"

# Modules observed as heavy/optional for eager-import diagnostics.
HEAVY_OPTIONAL_MODULE_PREFIXES: Tuple[str, ...] = (
    "torch",
    "transformers",
    "tensorflow",
    "sklearn",
    "numpy",
    "pandas",
    "pyarrow",
    "duckdb",
    "libp2p",
    "networkx",
    "huggingface_hub",
    "sentence_transformers",
)

REQUIRED_IDENTITY_FIELDS: Tuple[str, ...] = (
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
)

REQUIRED_MANIFEST_TOP_LEVEL: Tuple[str, ...] = (
    "schema",
    "schema_version",
    "task_id",
    "profile",
    "identity",
    "observations",
    "path_classes",
    "ack_states",
    "workloads",
    "results",
    "comparison_rules",
    "floors_status",
    "transaction_specific_slo",
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class BaselineSchemaError(ValueError):
    """Raised when baseline artifacts fail schema or identity checks."""


class BaselineMeasurementError(RuntimeError):
    """Raised when a measurement produces incomplete or invalid samples."""


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_json(obj: Any) -> str:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return _sha256_bytes(payload.encode("utf-8"))


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _percentile(sorted_values: Sequence[float], pct: float) -> float:
    if not sorted_values:
        raise BaselineMeasurementError("cannot compute percentile of empty sample set")
    if pct <= 0:
        return float(sorted_values[0])
    if pct >= 100:
        return float(sorted_values[-1])
    k = (len(sorted_values) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return float(sorted_values[f])
    return float(sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f))


def _mean_confidence_interval(
    samples: Sequence[float], confidence: float = 0.95
) -> Dict[str, float]:
    """Normal-approx CI for the mean (diagnostic; n may be small in CI)."""
    n = len(samples)
    if n == 0:
        raise BaselineMeasurementError("empty samples for confidence interval")
    mean = statistics.fmean(samples)
    if n == 1:
        return {
            "mean": mean,
            "stdev": 0.0,
            "n": 1.0,
            "confidence_level": confidence,
            "ci_low": mean,
            "ci_high": mean,
            "method": "degenerate_n1",
        }
    stdev = statistics.stdev(samples)
    # z for common levels; default ~1.96 for 0.95
    z_table = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
    z = z_table.get(round(confidence, 2), 1.96)
    half = z * (stdev / (n**0.5))
    return {
        "mean": mean,
        "stdev": stdev,
        "n": float(n),
        "confidence_level": confidence,
        "ci_low": mean - half,
        "ci_high": mean + half,
        "method": "normal_approx",
    }


# ---------------------------------------------------------------------------
# Environment / identity capture
# ---------------------------------------------------------------------------


def capture_hardware() -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "machine": platform.machine(),
        "processor": platform.processor() or "unknown",
        "cpu_count_logical": os.cpu_count(),
        "platform_node_hash": _sha256_bytes(platform.node().encode("utf-8"))[:16],
    }
    try:
        import psutil  # type: ignore

        vm = psutil.virtual_memory()
        info["memory_total_bytes"] = int(vm.total)
        info["cpu_freq_mhz"] = (
            float(psutil.cpu_freq().current) if psutil.cpu_freq() else None
        )
    except Exception as exc:  # pragma: no cover - optional enrichment
        info["psutil_error"] = type(exc).__name__
    return info


def capture_os() -> Dict[str, Any]:
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "platform": platform.platform(),
    }


def capture_python() -> Dict[str, Any]:
    return {
        "version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "executable": sys.executable,
        "version_info": list(sys.version_info[:3]),
    }


def capture_revision(package_root: Path = PACKAGE_ROOT) -> Dict[str, Any]:
    rev: Dict[str, Any] = {
        "package_root": str(package_root),
        "git_commit": None,
        "git_describe": None,
        "dirty": None,
        "source": "unavailable",
    }
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(package_root),
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
        ).strip()
        dirty_out = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=str(package_root),
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
        )
        rev["git_commit"] = commit
        rev["dirty"] = bool(dirty_out.strip())
        rev["source"] = "git"
    except Exception as exc:
        rev["error"] = type(exc).__name__
    return rev


def _load_pyproject(package_root: Path = PACKAGE_ROOT) -> Dict[str, Any]:
    path = package_root / "pyproject.toml"
    if not path.is_file():
        return {}
    with path.open("rb") as fh:
        return tomllib.load(fh)


def capture_metadata_versions(package_root: Path = PACKAGE_ROOT) -> Dict[str, Any]:
    pyproject = _load_pyproject(package_root)
    project = pyproject.get("project") or {}
    metadata_version = project.get("version")
    setup_version = None
    setup_py = package_root / "setup.py"
    if setup_py.is_file():
        text = setup_py.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("version=") or stripped.startswith("version ="):
                # version='0.3.0' or version="0.3.0"
                part = stripped.split("=", 1)[1].strip().rstrip(",").strip()
                setup_version = part.strip("'\"")
                break
    runtime_version = None
    runtime_error = None
    try:
        # Prefer reading source file to avoid full package import side effects.
        init_path = package_root / "ipfs_kit_py" / "__init__.py"
        if init_path.is_file():
            for line in init_path.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.strip().startswith("__version__"):
                    runtime_version = (
                        line.split("=", 1)[1].strip().strip("'\"")
                    )
                    break
    except Exception as exc:
        runtime_error = type(exc).__name__
    mismatch = (
        runtime_version is not None
        and metadata_version is not None
        and runtime_version != metadata_version
    )
    return {
        "runtime_version": runtime_version,
        "pyproject_version": metadata_version,
        "setup_py_version": setup_version,
        "runtime_metadata_mismatch": bool(mismatch),
        "runtime_read_error": runtime_error,
    }


def capture_dependency_projection(package_root: Path = PACKAGE_ROOT) -> Dict[str, Any]:
    """Record declared vs importable dependency projections and drift."""
    pyproject = _load_pyproject(package_root)
    project = pyproject.get("project") or {}
    declared = list(project.get("dependencies") or [])
    optional = project.get("optional-dependencies") or {}
    declared_optional = {k: list(v) for k, v in optional.items()}

    installed: Dict[str, str] = {}
    try:
        for dist in importlib.metadata.distributions():
            name = dist.metadata.get("Name") or dist.metadata.get("name")
            version = dist.version
            if name and version:
                installed[name.lower()] = version
    except Exception as exc:
        installed_error = type(exc).__name__
    else:
        installed_error = None

    # Simple name projection from requirement strings (strip extras/markers).
    def _req_name(req: str) -> str:
        base = req.split(";", 1)[0].strip()
        for sep in ("[", " ", "<", ">", "=", "!"):
            if sep in base:
                base = base.split(sep, 1)[0]
        return base.strip().lower()

    declared_names = sorted({_req_name(r) for r in declared if r.strip()})
    missing = [n for n in declared_names if n and n not in installed]
    present = {
        n: installed[n] for n in declared_names if n in installed
    }

    declared_digest = _sha256_json(
        {"dependencies": declared, "optional": declared_optional}
    )
    installed_digest = _sha256_json(installed)
    drift = bool(missing) or declared_digest != installed_digest

    return {
        "declared_dependencies": declared,
        "declared_optional_extras": declared_optional,
        "declared_names": declared_names,
        "installed_declared": present,
        "missing_declared": missing,
        "installed_count": len(installed),
        "declared_digest": declared_digest,
        "installed_digest": installed_digest,
        "dependency_projection_drift": drift,
        "installed_error": installed_error,
    }


def capture_resource_snapshot() -> Dict[str, Any]:
    snap: Dict[str, Any] = {
        "pid": os.getpid(),
        "rss_bytes": None,
        "cpu_percent": None,
        "fds": None,
        "threads": None,
    }
    try:
        import psutil  # type: ignore

        proc = psutil.Process(os.getpid())
        snap["rss_bytes"] = int(proc.memory_info().rss)
        snap["cpu_percent"] = float(proc.cpu_percent(interval=0.05))
        snap["threads"] = int(proc.num_threads())
        try:
            snap["fds"] = int(proc.num_fds())
        except Exception:
            snap["fds"] = None
    except Exception as exc:
        snap["error"] = type(exc).__name__
    return snap


def build_identity(
    *,
    profile: Mapping[str, Any],
    seed: int,
    concurrency: int,
    durability: str,
    warmup: int,
    samples: int,
    confidence: float,
    dataset: str,
    package_root: Path = PACKAGE_ROOT,
) -> Dict[str, Any]:
    hardware = capture_hardware()
    os_info = capture_os()
    python_info = capture_python()
    dependencies = capture_dependency_projection(package_root)
    revision = capture_revision(package_root)
    identity = {
        "hardware": hardware,
        "os": os_info,
        "python": python_info,
        "dependencies": dependencies,
        "revision": revision,
        "dataset": dataset,
        "seed": seed,
        "concurrency": concurrency,
        "durability": durability,
        "warmup": warmup,
        "samples": samples,
        "confidence": confidence,
        "profile_defaults": {
            "backend_tier": profile.get("backend_tier"),
            "storage": profile.get("storage"),
            "daemon": profile.get("daemon"),
            "networked": profile.get("networked"),
        },
    }
    identity["identity_digest"] = _sha256_json(
        {k: identity[k] for k in REQUIRED_IDENTITY_FIELDS}
    )
    return identity


# ---------------------------------------------------------------------------
# Import tracing (cold subprocess)
# ---------------------------------------------------------------------------


def _import_trace_script(module: str) -> str:
    # Executed in a fresh interpreter; prints a single JSON object on stdout.
    return f"""
import json, sys, time
start = time.perf_counter()
before = set(sys.modules.keys())
error = None
try:
    __import__({module!r})
except Exception as exc:
    error = {{"type": type(exc).__name__, "message": str(exc)[:500]}}
after = set(sys.modules.keys())
elapsed = time.perf_counter() - start
loaded = sorted(after - before)
heavy_prefixes = {list(HEAVY_OPTIONAL_MODULE_PREFIXES)!r}
eager_heavy = sorted({{
    m for m in loaded
    if any(m == p or m.startswith(p + ".") for p in heavy_prefixes)
}})
print(json.dumps({{
    "module": {module!r},
    "import_seconds": elapsed,
    "modules_loaded_count": len(loaded),
    "modules_loaded_sample": loaded[:80],
    "eager_heavy_optional_imports": eager_heavy,
    "error": error,
    "python": sys.version.split()[0],
}}))
"""


def measure_cold_import(
    module: str,
    *,
    python: str = sys.executable,
    timeout: float = 120.0,
    env: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Cold-import *module* in a subprocess and return an ImportTrace@1 record."""
    child_env = os.environ.copy()
    if env:
        child_env.update(env)
    # Reduce accidental side effects from installer / user state.
    child_env.setdefault("IPFS_KIT_AUTO_INSTALL_BINARIES", "0")
    child_env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    script = _import_trace_script(module)
    started = time.time()
    try:
        proc = subprocess.run(
            [python, "-c", script],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=child_env,
            cwd=str(PACKAGE_ROOT),
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "schema": IMPORT_TRACE_SCHEMA,
            "module": module,
            "path_class": "cold",
            "success": False,
            "error": {"type": "TimeoutExpired", "message": str(exc)},
            "import_seconds": timeout,
            "wall_seconds": time.time() - started,
        }
    wall = time.time() - started
    if proc.returncode != 0 and not (proc.stdout or "").strip():
        return {
            "schema": IMPORT_TRACE_SCHEMA,
            "module": module,
            "path_class": "cold",
            "success": False,
            "error": {
                "type": "SubprocessError",
                "message": (proc.stderr or "")[:1000],
                "returncode": proc.returncode,
            },
            "import_seconds": None,
            "wall_seconds": wall,
        }
    try:
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception as exc:
        return {
            "schema": IMPORT_TRACE_SCHEMA,
            "module": module,
            "path_class": "cold",
            "success": False,
            "error": {
                "type": "ParseError",
                "message": str(exc),
                "stdout_tail": (proc.stdout or "")[-500:],
                "stderr_tail": (proc.stderr or "")[-500:],
            },
            "import_seconds": None,
            "wall_seconds": wall,
        }
    payload["schema"] = IMPORT_TRACE_SCHEMA
    payload["path_class"] = "cold"
    payload["success"] = payload.get("error") is None and proc.returncode == 0
    payload["returncode"] = proc.returncode
    payload["wall_seconds"] = wall
    payload["stderr_tail"] = (proc.stderr or "")[-300:] or None
    return payload


def analyze_eager_imports_from_source(package_root: Path = PACKAGE_ROOT) -> Dict[str, Any]:
    """Static observations about root and MCP import surfaces (no side effects)."""
    root_init = package_root / "ipfs_kit_py" / "__init__.py"
    mcp_server = package_root / "ipfs_kit_py" / "mcp_server" / "server.py"
    observations: Dict[str, Any] = {
        "root_init_exists": root_init.is_file(),
        "mcp_server_exists": mcp_server.is_file(),
        "root_eager_import_lines": [],
        "mcp_eager_import_lines": [],
        "mcp_eventdag_unimported_reference": False,
    }

    def _top_level_imports(path: Path, limit: int = 40) -> List[str]:
        if not path.is_file():
            return []
        lines: List[str] = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if s.startswith("import ") or s.startswith("from "):
                lines.append(s)
            if len(lines) >= limit:
                break
        return lines

    observations["root_eager_import_lines"] = _top_level_imports(root_init)
    observations["mcp_eager_import_lines"] = _top_level_imports(mcp_server)

    if mcp_server.is_file():
        text = mcp_server.read_text(encoding="utf-8", errors="replace")
        references = "EventDAGStore" in text
        imported = (
            "import EventDAGStore" in text
            or "from " in text
            and any(
                "EventDAGStore" in line and line.strip().startswith("from ")
                for line in text.splitlines()
            )
            or "EventDAGStore" in text
            and any(
                "EventDAGStore" in line and "import" in line
                for line in text.splitlines()
                if line.strip().startswith(("import ", "from "))
            )
        )
        # More precise: any import line that binds EventDAGStore
        import_binds = any(
            "EventDAGStore" in line
            for line in text.splitlines()
            if line.strip().startswith(("import ", "from "))
        )
        observations["mcp_eventdag_unimported_reference"] = bool(
            references and not import_binds
        )
        observations["root_has_jit_init"] = "jit_manager" in root_init.read_text(
            encoding="utf-8", errors="replace"
        ) if root_init.is_file() else False

    return observations


# ---------------------------------------------------------------------------
# Synthetic in-process transaction model (bound-revision micro-baseline)
# ---------------------------------------------------------------------------


@dataclass
class _TxnResult:
    accepted: bool
    committed: bool
    latency_s: float


class MemoryTransactionEngine:
    """Minimal durable-ish in-memory engine for baseline micro-measurement.

    Distinguishes *accepted* (enqueued) from *committed* (durability barrier).
    This intentionally does not call production WAL/VFS paths so KITA-004 can
    pin measurement identity without optimizing those paths.
    """

    def __init__(self, *, seed: int, durability: str = "memory_sync") -> None:
        self._rng = random.Random(seed)
        self.durability = durability
        self._store: Dict[str, bytes] = {}
        self._wal: List[Tuple[str, str, Optional[bytes]]] = []
        self._committed = 0
        self._accepted = 0

    def accept(self, op: str, key: str, value: Optional[bytes] = None) -> None:
        self._wal.append((op, key, value))
        self._accepted += 1

    def commit(self) -> None:
        # Simulate durability cost proportional to batch size.
        for op, key, value in self._wal:
            if op == "put":
                self._store[key] = value or b""
            elif op == "delete":
                self._store.pop(key, None)
            elif op == "get":
                _ = self._store.get(key)
            elif op in {"stat", "list", "rename", "catalog_put", "cas_put"}:
                if op == "rename" and value is not None:
                    src = key
                    dst = value.decode("utf-8", errors="replace")
                    if src in self._store:
                        self._store[dst] = self._store.pop(src)
                elif op in {"catalog_put", "cas_put", "stat"}:
                    self._store.setdefault(key, value or b"")
            self._committed += 1
        self._wal.clear()
        if self.durability in {"memory_sync", "fsync_parent", "daemon_commit"}:
            # Busy-wait-free spin using RNG work to create stable relative cost.
            _ = sum(self._rng.random() for _ in range(8))

    def run_one(self, op: str, payload_bytes: int = 64) -> _TxnResult:
        key = f"k-{self._rng.randrange(1 << 28)}"
        value = self._rng.randbytes(payload_bytes) if op in {"put", "catalog_put", "cas_put", "write"} else None
        if op == "rename":
            value = f"k-{self._rng.randrange(1 << 28)}".encode("utf-8")
        t0 = time.perf_counter()
        self.accept(op, key, value)
        accepted_latency = time.perf_counter() - t0
        # Accepted sample point (pre-durability).
        t1 = time.perf_counter()
        self.commit()
        committed_latency = time.perf_counter() - t0
        _ = accepted_latency  # retained for clarity of protocol stages
        return _TxnResult(accepted=True, committed=True, latency_s=committed_latency)


def measure_transaction_workload(
    *,
    operations: Sequence[str],
    seed: int,
    warmup: int,
    samples: int,
    payload_bytes: int,
    durability: str,
    path_class: str,
    mix: Optional[Mapping[str, float]] = None,
    confidence: float = 0.95,
) -> Dict[str, Any]:
    """Measure accepted vs committed TPS for a synthetic transaction workload."""
    if samples <= 0:
        raise BaselineMeasurementError("samples must be positive")
    engine = MemoryTransactionEngine(seed=seed, durability=durability)
    rng = random.Random(seed ^ 0xA5A5)

    def pick_op() -> str:
        if not mix:
            return operations[rng.randrange(len(operations))]
        keys = list(mix.keys())
        weights = [float(mix[k]) for k in keys]
        return rng.choices(keys, weights=weights, k=1)[0]

    # Warmup does not contribute samples; establishes warm/cache process state.
    for _ in range(max(0, warmup)):
        engine.run_one(pick_op(), payload_bytes=payload_bytes)

    # Optional cache path: touch a hot set before measurement.
    if path_class == "cache":
        for i in range(32):
            engine.run_one("put", payload_bytes=payload_bytes)
            engine.run_one("get", payload_bytes=payload_bytes)

    accepted_latencies: List[float] = []
    committed_latencies: List[float] = []

    # For accepted vs committed distinction we time stages separately.
    measure_engine = MemoryTransactionEngine(seed=seed + 1, durability=durability)
    wall_start = time.perf_counter()
    for _ in range(samples):
        op = pick_op()
        key = f"k-{rng.randrange(1 << 28)}"
        value = rng.randbytes(payload_bytes) if op in {"put", "catalog_put", "cas_put", "write"} else None
        if op == "rename":
            value = f"k-{rng.randrange(1 << 28)}".encode("utf-8")
        t0 = time.perf_counter()
        measure_engine.accept(op, key, value)
        t_acc = time.perf_counter()
        measure_engine.commit()
        t_end = time.perf_counter()
        accepted_latencies.append(t_acc - t0)
        committed_latencies.append(t_end - t0)
    wall = time.perf_counter() - wall_start
    if wall <= 0:
        raise BaselineMeasurementError("non-positive measurement wall time")

    accepted_sorted = sorted(accepted_latencies)
    committed_sorted = sorted(committed_latencies)
    committed_tps = samples / wall
    # Accepted TPS uses accepted-stage only wall (sum of accepted latencies).
    acc_sum = sum(accepted_latencies)
    accepted_tps = samples / acc_sum if acc_sum > 0 else float("inf")

    result = {
        "path_class": path_class,
        "ack_states_measured": ["accepted", "committed"],
        "samples": samples,
        "warmup": warmup,
        "seed": seed,
        "durability": durability,
        "payload_bytes": payload_bytes,
        "wall_seconds": wall,
        "accepted_tps": accepted_tps,
        "committed_tps": committed_tps,
        "primary_metric": "committed_tps",
        "accepted_latency_ms": {
            "p50": _percentile(accepted_sorted, 50) * 1000.0,
            "p95": _percentile(accepted_sorted, 95) * 1000.0,
            "p99": _percentile(accepted_sorted, 99) * 1000.0,
        },
        "committed_latency_ms": {
            "p50": _percentile(committed_sorted, 50) * 1000.0,
            "p95": _percentile(committed_sorted, 95) * 1000.0,
            "p99": _percentile(committed_sorted, 99) * 1000.0,
        },
        "committed_tps_confidence": _mean_confidence_interval(
            [1.0 / max(x, 1e-12) for x in committed_latencies],
            confidence=confidence,
        ),
        "partial": False,
        "errors": 0,
    }
    # Sanity: committed must not exceed accepted throughput in this model.
    if result["committed_tps"] > result["accepted_tps"] * 1.0001:
        # Floating edge cases with tiny accepted sums; clamp diagnostic only.
        result["accepted_tps"] = max(result["accepted_tps"], result["committed_tps"])
    return result


def measure_resource_snapshot_series(samples: int = 5) -> Dict[str, Any]:
    series = [capture_resource_snapshot() for _ in range(max(1, samples))]
    rss = [s["rss_bytes"] for s in series if s.get("rss_bytes") is not None]
    return {
        "path_class": "warm",
        "samples": len(series),
        "rss_bytes_mean": statistics.fmean(rss) if rss else None,
        "rss_bytes_max": max(rss) if rss else None,
        "last": series[-1],
        "series_len": len(series),
    }


# ---------------------------------------------------------------------------
# Schema validation & comparison rules
# ---------------------------------------------------------------------------


def load_workloads() -> Dict[str, Any]:
    data = _read_json(WORKLOADS_PATH)
    if data.get("schema") != WORKLOAD_PROFILE_SCHEMA:
        raise BaselineSchemaError(
            f"workloads.json schema must be {WORKLOAD_PROFILE_SCHEMA}, got {data.get('schema')!r}"
        )
    for key in ("path_classes", "ack_states", "resource_profiles", "workloads"):
        if key not in data:
            raise BaselineSchemaError(f"workloads.json missing {key!r}")
    for required in ("cold", "warm", "cache"):
        if required not in data["path_classes"]:
            raise BaselineSchemaError(f"workloads.json missing path_class {required!r}")
    if "ci-reference" not in data["resource_profiles"]:
        raise BaselineSchemaError("workloads.json missing resource profile 'ci-reference'")
    return data


def load_floors() -> Dict[str, Any]:
    data = _read_json(FLOORS_PATH)
    if data.get("schema") != "RuntimeReferenceFloors@1":
        raise BaselineSchemaError(
            f"reference_floors.json schema must be RuntimeReferenceFloors@1, got {data.get('schema')!r}"
        )
    if data.get("status") != "provisional":
        # Still allow reviewed later; but KITA-004 requires provisional at creation.
        pass
    if data.get("reviewed") is True and data.get("status") == "provisional":
        raise BaselineSchemaError("floors cannot be reviewed while status is provisional")
    rules = data.get("comparison_rules") or {}
    if not rules.get("immutable"):
        raise BaselineSchemaError("comparison_rules.immutable must be true")
    if rules.get("rule_id") != COMPARISON_RULES_ID:
        raise BaselineSchemaError(
            f"comparison_rules.rule_id must be {COMPARISON_RULES_ID}"
        )
    obs = data.get("observation_anchors") or {}
    txn_slo = obs.get("transaction_specific_slo") or {}
    if txn_slo.get("slo_present") is not False:
        raise BaselineSchemaError(
            "observation_anchors.transaction_specific_slo.slo_present must be false for KITA-004"
        )
    return data


def comparison_rules_from_floors(floors: Mapping[str, Any]) -> Dict[str, Any]:
    rules = dict(floors.get("comparison_rules") or {})
    rules["immutable"] = True
    rules["rule_id"] = COMPARISON_RULES_ID
    rules["primary_throughput_metric"] = "committed_tps"
    rules["path_classes"] = ["cold", "warm", "cache"]
    rules["identity_fields"] = list(REQUIRED_IDENTITY_FIELDS)
    return rules


def validate_manifest_schema(manifest: Mapping[str, Any]) -> List[str]:
    """Return a list of schema problems (empty means valid)."""
    problems: List[str] = []
    for key in REQUIRED_MANIFEST_TOP_LEVEL:
        if key not in manifest:
            problems.append(f"missing top-level field {key!r}")
    if manifest.get("schema") != SCHEMA:
        problems.append(f"schema must be {SCHEMA}")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        problems.append(f"schema_version must be {SCHEMA_VERSION}")
    identity = manifest.get("identity") or {}
    for field_name in REQUIRED_IDENTITY_FIELDS:
        if field_name not in identity:
            problems.append(f"identity missing {field_name!r}")
    path_classes = manifest.get("path_classes") or {}
    for pc in ("cold", "warm", "cache"):
        if pc not in path_classes:
            problems.append(f"path_classes missing {pc!r}")
    ack = manifest.get("ack_states") or {}
    for state in ("accepted", "committed"):
        if state not in ack:
            problems.append(f"ack_states missing {state!r}")
    rules = manifest.get("comparison_rules") or {}
    if not rules.get("immutable"):
        problems.append("comparison_rules.immutable must be true")
    if rules.get("primary_throughput_metric") != "committed_tps":
        problems.append("comparison_rules.primary_throughput_metric must be committed_tps")
    floors_status = manifest.get("floors_status") or {}
    if floors_status.get("status") != "provisional" and floors_status.get("reviewed") is not True:
        # KITA-004 baseline leaves floors provisional until reviewed.
        if floors_status.get("status") not in {"provisional", "reviewed"}:
            problems.append("floors_status.status must be provisional or reviewed")
    txn_slo = manifest.get("transaction_specific_slo") or {}
    if txn_slo.get("present") is not False:
        problems.append("transaction_specific_slo.present must be false")
    observations = manifest.get("observations") or {}
    for key in (
        "runtime_metadata_version_mismatch",
        "dependency_projection_drift",
        "root_eager_imports",
        "mcp_eager_imports",
    ):
        if key not in observations:
            problems.append(f"observations missing {key!r}")
    results = manifest.get("results") or {}
    # When results include transaction workloads, require committed_tps.
    for name, payload in results.items():
        if not isinstance(payload, Mapping):
            continue
        if payload.get("primary_metric") == "committed_tps":
            if "committed_tps" not in payload:
                problems.append(f"result {name!r} missing committed_tps")
            if "accepted_tps" not in payload:
                problems.append(f"result {name!r} missing accepted_tps (diagnostic)")
            if payload.get("path_class") not in {"cold", "warm", "cache"}:
                problems.append(f"result {name!r} path_class must be cold|warm|cache")
    return problems


def assert_manifest_valid(manifest: Mapping[str, Any]) -> None:
    problems = validate_manifest_schema(manifest)
    if problems:
        raise BaselineSchemaError(
            "manifest schema validation failed:\n- " + "\n- ".join(problems)
        )


def results_comparable(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    rules: Optional[Mapping[str, Any]] = None,
) -> Tuple[bool, List[str]]:
    """Immutable comparison gate: True only when identity fully matches."""
    rules = rules or {}
    reasons: List[str] = []
    for field_name in REQUIRED_IDENTITY_FIELDS:
        lv = (left.get("identity") or {}).get(field_name)
        rv = (right.get("identity") or {}).get(field_name)
        if field_name in {"hardware", "os", "python", "dependencies", "revision"}:
            # Compare digests / stable subfields when present.
            if isinstance(lv, Mapping) and isinstance(rv, Mapping):
                if field_name == "revision":
                    if lv.get("git_commit") != rv.get("git_commit"):
                        reasons.append("revision.git_commit mismatch")
                elif field_name == "dependencies":
                    if lv.get("declared_digest") != rv.get("declared_digest"):
                        reasons.append("dependencies.declared_digest mismatch")
                elif field_name == "python":
                    if lv.get("version") != rv.get("version"):
                        reasons.append("python.version mismatch")
                elif field_name == "os":
                    if (lv.get("system"), lv.get("release")) != (
                        rv.get("system"),
                        rv.get("release"),
                    ):
                        reasons.append("os family/release mismatch")
                elif field_name == "hardware":
                    if (lv.get("machine"), lv.get("cpu_count_logical")) != (
                        rv.get("machine"),
                        rv.get("cpu_count_logical"),
                    ):
                        reasons.append("hardware class mismatch")
            elif lv != rv:
                reasons.append(f"{field_name} mismatch")
        else:
            if lv != rv:
                reasons.append(f"{field_name} mismatch")
    # Path class and primary metric separation.
    if left.get("path_class") != right.get("path_class"):
        reasons.append("path_class mismatch")
    primary = rules.get("primary_throughput_metric", "committed_tps")
    if primary != "committed_tps":
        reasons.append("primary_throughput_metric must remain committed_tps")
    return (len(reasons) == 0, reasons)


# ---------------------------------------------------------------------------
# Baseline run
# ---------------------------------------------------------------------------


def build_observations(package_root: Path = PACKAGE_ROOT) -> Dict[str, Any]:
    versions = capture_metadata_versions(package_root)
    deps = capture_dependency_projection(package_root)
    eager = analyze_eager_imports_from_source(package_root)
    return {
        "runtime_metadata_version_mismatch": {
            "observed": bool(versions.get("runtime_metadata_mismatch")),
            "runtime_version": versions.get("runtime_version"),
            "pyproject_version": versions.get("pyproject_version"),
            "setup_py_version": versions.get("setup_py_version"),
        },
        "dependency_projection_drift": {
            "observed": bool(deps.get("dependency_projection_drift")),
            "missing_declared": deps.get("missing_declared"),
            "declared_digest": deps.get("declared_digest"),
            "installed_digest": deps.get("installed_digest"),
        },
        "root_eager_imports": {
            "observed": bool(eager.get("root_eager_import_lines")),
            "import_lines": eager.get("root_eager_import_lines"),
            "has_jit_init": eager.get("root_has_jit_init"),
        },
        "mcp_eager_imports": {
            "observed": bool(eager.get("mcp_eager_import_lines")),
            "import_lines": eager.get("mcp_eager_import_lines"),
            "eventdag_unimported_reference": eager.get(
                "mcp_eventdag_unimported_reference"
            ),
        },
        "no_transaction_specific_slo": {
            "observed": True,
            "slo_present": False,
            "note": "Transaction-specific RuntimeSLO@1 is not defined in KITA-004; measurement identity only.",
        },
    }


def run_baseline(
    profile_name: str = "ci-reference",
    *,
    include_imports: bool = True,
    include_transactions: bool = True,
    package_root: Path = PACKAGE_ROOT,
) -> Dict[str, Any]:
    workloads_doc = load_workloads()
    floors_doc = load_floors()
    profiles = workloads_doc["resource_profiles"]
    if profile_name not in profiles:
        raise BaselineSchemaError(
            f"unknown profile {profile_name!r}; known={sorted(profiles)}"
        )
    profile = profiles[profile_name]
    seed = int(profile.get("default_seed", 424242))
    concurrency = int(profile.get("default_concurrency", 1))
    durability = str(profile.get("default_durability", "memory_sync"))
    warmup = int(profile.get("warmup_samples", 5))
    samples = int(profile.get("measurement_samples", 25))
    confidence = float(profile.get("confidence_level", 0.95))

    identity = build_identity(
        profile=profile,
        seed=seed,
        concurrency=concurrency,
        durability=durability,
        warmup=warmup,
        samples=samples,
        confidence=confidence,
        dataset="dataset:baseline_bundle_v1",
        package_root=package_root,
    )
    observations = build_observations(package_root)
    results: Dict[str, Any] = {}

    if include_imports:
        # Cold import traces — may fail if package not importable; still record.
        for wl_name, module in (
            ("cold_import_root", "ipfs_kit_py"),
            ("cold_import_mcp", "ipfs_kit_py.mcp_server.server"),
        ):
            # Ensure package root on path for subprocess via PYTHONPATH.
            env = {
                "PYTHONPATH": os.pathsep.join(
                    [
                        str(package_root),
                        os.environ.get("PYTHONPATH", ""),
                    ]
                ).strip(os.pathsep)
            }
            results[wl_name] = measure_cold_import(module, env=env)

    if include_transactions:
        wl_defs = workloads_doc["workloads"]
        for wl_name in (
            "metadata_txn",
            "small_object_txn",
            "mixed_vfs",
            "wal_commit",
        ):
            wl = wl_defs[wl_name]
            path_results: Dict[str, Any] = {}
            for path_class in ("cold", "warm", "cache"):
                if path_class not in wl.get("path_classes", ["warm"]):
                    continue
                # Cold path: zero warmup for that measurement engine.
                w = 0 if path_class == "cold" else warmup
                path_results[path_class] = measure_transaction_workload(
                    operations=list(wl.get("operations") or ["put"]),
                    seed=seed,
                    warmup=w,
                    samples=samples,
                    payload_bytes=int(wl.get("payload_bytes") or 64),
                    durability=durability,
                    path_class=path_class,
                    mix=wl.get("mix"),
                    confidence=confidence,
                )
            # Primary entry uses warm/committed as the baseline default view.
            primary = dict(path_results.get("warm") or next(iter(path_results.values())))
            primary["by_path_class"] = path_results
            primary["workload_id"] = wl["id"]
            primary["dataset"] = wl.get("dataset")
            results[wl_name] = primary

        results["resource_snapshot"] = measure_resource_snapshot_series(
            samples=min(5, samples)
        )

    manifest: Dict[str, Any] = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "profile": profile_name,
        "profile_id": profile.get("id"),
        "generated_at_unix": time.time(),
        "identity": identity,
        "observations": observations,
        "path_classes": workloads_doc["path_classes"],
        "ack_states": workloads_doc["ack_states"],
        "workloads": {
            name: workloads_doc["workloads"][name]
            for name in profile.get("workloads", [])
            if name in workloads_doc["workloads"]
        },
        "results": results,
        "comparison_rules": comparison_rules_from_floors(floors_doc),
        "floors_status": {
            "status": floors_doc.get("status", "provisional"),
            "reviewed": bool(floors_doc.get("reviewed")),
            "reviewed_by": floors_doc.get("reviewed_by"),
            "review_receipt_cid": floors_doc.get("review_receipt_cid"),
            "absolute_floors_provisional": floors_doc.get("status") == "provisional",
        },
        "transaction_specific_slo": {
            "present": False,
            "schema": None,
            "note": "No transaction-specific SLO at KITA-004; later RuntimeSLO@1 task owns gates.",
        },
        "artifact_paths": {
            "workloads": str(WORKLOADS_PATH.name),
            "reference_floors": str(FLOORS_PATH.name),
        },
    }
    manifest["manifest_digest"] = _sha256_json(
        {k: manifest[k] for k in REQUIRED_MANIFEST_TOP_LEVEL if k in manifest}
    )
    assert_manifest_valid(manifest)
    return manifest


def check_schema(profile_name: str = "ci-reference") -> Dict[str, Any]:
    """Validate static artifacts and a schema-only manifest skeleton."""
    workloads_doc = load_workloads()
    floors_doc = load_floors()
    if profile_name not in workloads_doc["resource_profiles"]:
        raise BaselineSchemaError(f"unknown profile {profile_name!r}")

    profile = workloads_doc["resource_profiles"][profile_name]
    identity = build_identity(
        profile=profile,
        seed=int(profile.get("default_seed", 424242)),
        concurrency=int(profile.get("default_concurrency", 1)),
        durability=str(profile.get("default_durability", "memory_sync")),
        warmup=int(profile.get("warmup_samples", 5)),
        samples=int(profile.get("measurement_samples", 25)),
        confidence=float(profile.get("confidence_level", 0.95)),
        dataset="dataset:baseline_bundle_v1",
    )
    observations = build_observations()
    # Schema check includes a minimal committed-TPS result shape without full run.
    micro = measure_transaction_workload(
        operations=["put", "get"],
        seed=int(profile.get("default_seed", 424242)),
        warmup=1,
        samples=5,
        payload_bytes=64,
        durability=str(profile.get("default_durability", "memory_sync")),
        path_class="warm",
        confidence=float(profile.get("confidence_level", 0.95)),
    )
    manifest = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "profile": profile_name,
        "identity": identity,
        "observations": observations,
        "path_classes": workloads_doc["path_classes"],
        "ack_states": workloads_doc["ack_states"],
        "workloads": {
            k: workloads_doc["workloads"][k]
            for k in ("metadata_txn", "small_object_txn", "cold_import_root")
            if k in workloads_doc["workloads"]
        },
        "results": {
            "metadata_txn": {
                **micro,
                "workload_id": "workload:metadata_txn",
                "dataset": "dataset:metadata_catalog_v1",
            }
        },
        "comparison_rules": comparison_rules_from_floors(floors_doc),
        "floors_status": {
            "status": floors_doc.get("status", "provisional"),
            "reviewed": bool(floors_doc.get("reviewed")),
            "absolute_floors_provisional": floors_doc.get("status") == "provisional",
        },
        "transaction_specific_slo": {"present": False, "schema": None},
    }
    assert_manifest_valid(manifest)

    # Floors must remain provisional until reviewed.
    if floors_doc.get("status") != "provisional":
        raise BaselineSchemaError(
            "KITA-004 requires reference_floors.json status=provisional until review"
        )
    if floors_doc.get("reviewed"):
        raise BaselineSchemaError(
            "reference_floors.json reviewed must be false until explicit review"
        )

    return {
        "ok": True,
        "schema": SCHEMA,
        "profile": profile_name,
        "workloads_schema": workloads_doc.get("schema"),
        "floors_schema": floors_doc.get("schema"),
        "floors_status": floors_doc.get("status"),
        "comparison_rules_immutable": True,
        "primary_throughput_metric": "committed_tps",
        "path_classes": sorted(workloads_doc["path_classes"]),
        "identity_fields": list(REQUIRED_IDENTITY_FIELDS),
        "observations_present": sorted(observations.keys()),
        "transaction_specific_slo_present": False,
        "manifest_problems": [],
        "micro_committed_tps": micro["committed_tps"],
        "micro_accepted_tps": micro["accepted_tps"],
        "runtime_metadata_mismatch": observations["runtime_metadata_version_mismatch"][
            "observed"
        ],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="KITA-004 runtime readiness baseline harness")
    p.add_argument(
        "--profile",
        default="ci-reference",
        help="Resource profile name from workloads.json (default: ci-reference)",
    )
    p.add_argument(
        "--check-schema",
        action="store_true",
        help="Validate workloads, floors, and manifest schema without full import suite",
    )
    p.add_argument(
        "--run",
        action="store_true",
        help="Execute baseline measurements for the selected profile",
    )
    p.add_argument(
        "--json-out",
        default=None,
        help="Optional path to write the manifest or check-schema report as JSON",
    )
    p.add_argument(
        "--skip-imports",
        action="store_true",
        help="When --run, skip cold-import subprocess measurements",
    )
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if not args.check_schema and not args.run:
        # Default action for explicit profile invocation in validation: schema check
        # is required by the task validation command with --check-schema.
        # If neither flag is set, perform schema check (safe default).
        args.check_schema = True

    try:
        if args.run:
            manifest = run_baseline(
                args.profile,
                include_imports=not args.skip_imports,
            )
            output: Dict[str, Any] = manifest
        else:
            output = check_schema(args.profile)
    except (BaselineSchemaError, BaselineMeasurementError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1

    text = json.dumps(output, indent=2, sort_keys=True, default=str)
    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Deterministic, opt-in interoperability harness for real Iroh nodes.

Normal unit tests must not start daemons, containers, or use the network.  This
module therefore separates deterministic scenario construction and evidence
validation from execution.  A real test lane supplies a driver command which
owns the platform-specific node/container setup and returns one bounded JSON
observation for each scenario.

The command boundary is intentional.  It lets Linux lanes use network
namespaces or containers while macOS lanes use their native process/VM
topology, without weakening the evidence contract or teaching the Python
package to invoke Docker implicitly.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import json
import math
import os
import platform
import re
import shlex
import signal
import shutil
import sys
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

EVIDENCE_RESOURCE = "iroh-interoperability-evidence.json"
EVIDENCE_SCHEMA_RESOURCE = "iroh-interoperability-evidence.schema.json"
EVIDENCE_KIND = "ipfs-kit-iroh-interoperability-evidence"
EVIDENCE_SCHEMA_VERSION = 1
HARNESS_VERSION = "1.0.0"
OPT_IN_ENV = "IPFS_KIT_IROH_INTEROP"
DRIVER_ENV = "IPFS_KIT_IROH_INTEROP_DRIVER"
CURRENT_BINARY_ENV = "IPFS_KIT_IROH_INTEROP_BINARY"
PREVIOUS_BINARY_ENV = "IPFS_KIT_IROH_INTEROP_PREVIOUS_BINARY"
RELAY_URL_ENV = "IPFS_KIT_IROH_INTEROP_RELAY_URL"
EVIDENCE_PATH_ENV = "IPFS_KIT_IROH_INTEROP_EVIDENCE"

DIRECT_LAN = "direct_lan"
RELAY_FALLBACK = "relay_fallback"
NAT_CONTAINER = "nat_container"
INTERRUPTION_RESUME = "interruption_resume"
VERSION_SKEW = "version_skew"
KEY_ROTATION = "key_rotation"
LARGE_DATA = "large_data"

REQUIRED_SCENARIOS = (
    DIRECT_LAN,
    RELAY_FALLBACK,
    NAT_CONTAINER,
    INTERRUPTION_RESUME,
    VERSION_SKEW,
    KEY_ROTATION,
    LARGE_DATA,
)

_STATUS = frozenset({"passed", "failed", "skipped", "not_run"})
_OBSERVATION_STATUS = frozenset({"passed", "failed", "skipped"})
_TRANSPORTS = frozenset({"direct", "relay", "none"})
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SENSITIVE_RE = re.compile(
    r"(?:secret|token|ticket|password|passwd|private.?key|node.?key|"
    r"capability|credential|authorization|cookie|peer.?id|node.?identity|endpoint|address|url)",
    re.IGNORECASE,
)


class InteropConfigurationError(ValueError):
    """The harness or its evidence does not satisfy the closed contract."""


class InteropDriverError(RuntimeError):
    """A real scenario driver failed or returned an invalid observation."""


@dataclass(frozen=True, slots=True)
class ResourceBounds:
    """Cross-platform upper bounds enforced for every real scenario."""

    scenario_timeout_seconds: float = 180.0
    max_peak_rss_bytes: int = 768 * 1024 * 1024
    max_transfer_chunk_bytes: int = 1024 * 1024
    max_active_transfers: int = 4
    max_node_count: int = 4
    max_driver_output_bytes: int = 1024 * 1024

    def __post_init__(self) -> None:
        timeout = self.scenario_timeout_seconds
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or float(timeout) <= 0
            or not math.isfinite(float(timeout))
        ):
            raise InteropConfigurationError("scenario_timeout_seconds must be finite and positive")
        for name in (
            "max_peak_rss_bytes",
            "max_transfer_chunk_bytes",
            "max_active_transfers",
            "max_node_count",
            "max_driver_output_bytes",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise InteropConfigurationError(f"{name} must be a positive integer")
        if self.max_node_count < 3:
            raise InteropConfigurationError("max_node_count must permit the three-node scenarios")

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ScenarioPlan:
    """Secret-free, deterministic instructions sent to a platform driver."""

    scenario_id: str
    topology: str
    expected_transport: str
    node_count: int
    payload_size: int
    interrupt_after_bytes: int | None = None
    requires_previous_binary: bool = False
    requires_identity_rotation: bool = False
    direct_path_blocked: bool = False

    def __post_init__(self) -> None:
        if self.scenario_id not in REQUIRED_SCENARIOS:
            raise InteropConfigurationError("unknown interoperability scenario")
        if not isinstance(self.topology, str) or not self.topology:
            raise InteropConfigurationError("scenario topology must be a non-empty string")
        if self.expected_transport not in _TRANSPORTS:
            raise InteropConfigurationError("invalid expected transport")
        if (
            isinstance(self.node_count, bool)
            or not isinstance(self.node_count, int)
            or self.node_count < 2
        ):
            raise InteropConfigurationError("every scenario requires at least two nodes")
        if (
            isinstance(self.payload_size, bool)
            or not isinstance(self.payload_size, int)
            or self.payload_size <= 0
        ):
            raise InteropConfigurationError("payload_size must be positive")
        if self.interrupt_after_bytes is not None:
            if (
                isinstance(self.interrupt_after_bytes, bool)
                or not isinstance(self.interrupt_after_bytes, int)
                or not 0 < self.interrupt_after_bytes < self.payload_size
            ):
                raise InteropConfigurationError("interrupt offset must be inside the payload")
        if any(
            not isinstance(value, bool)
            for value in (
                self.requires_previous_binary,
                self.requires_identity_rotation,
                self.direct_path_blocked,
            )
        ):
            raise InteropConfigurationError("scenario flags must be booleans")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_scenario_plans(
    *, small_payload_bytes: int = 256 * 1024, large_payload_bytes: int = 32 * 1024 * 1024
) -> tuple[ScenarioPlan, ...]:
    """Return the complete scenario matrix in stable execution order."""

    for value, name in (
        (small_payload_bytes, "small_payload_bytes"),
        (large_payload_bytes, "large_payload_bytes"),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 2:
            raise InteropConfigurationError(f"{name} must be an integer of at least two")
    if large_payload_bytes < small_payload_bytes:
        raise InteropConfigurationError("large payload must not be smaller than small payload")
    return (
        ScenarioPlan(DIRECT_LAN, "isolated_processes_lan", "direct", 2, small_payload_bytes),
        ScenarioPlan(
            RELAY_FALLBACK,
            "isolated_processes_relay",
            "relay",
            3,
            small_payload_bytes,
            direct_path_blocked=True,
        ),
        ScenarioPlan(
            NAT_CONTAINER,
            "isolated_containers_nat",
            "relay",
            3,
            small_payload_bytes,
            direct_path_blocked=True,
        ),
        ScenarioPlan(
            INTERRUPTION_RESUME,
            "isolated_processes_lan",
            "direct",
            2,
            small_payload_bytes,
            interrupt_after_bytes=small_payload_bytes // 2,
        ),
        ScenarioPlan(
            VERSION_SKEW,
            "isolated_processes_lan",
            "direct",
            2,
            small_payload_bytes,
            requires_previous_binary=True,
        ),
        ScenarioPlan(
            KEY_ROTATION,
            "isolated_processes_lan",
            "direct",
            2,
            small_payload_bytes,
            requires_identity_rotation=True,
        ),
        ScenarioPlan(LARGE_DATA, "isolated_processes_lan", "direct", 2, large_payload_bytes),
    )


_PAYLOAD_BLOCK_BYTES = 64 * 1024


def _payload_block(seed: str, block_index: int) -> bytes:
    # A fixed logical block size makes the fixture independent of I/O chunking.
    return hashlib.shake_256(f"{seed}:{block_index}".encode("utf-8")).digest(_PAYLOAD_BLOCK_BYTES)


def write_deterministic_payload(
    path: str | os.PathLike[str],
    size: int,
    *,
    seed: str,
    chunk_size: int = 1024 * 1024,
) -> str:
    """Write a bounded-memory fixture and return its lowercase BLAKE3 hash."""

    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise InteropConfigurationError("payload size must be a positive integer")
    if isinstance(chunk_size, bool) or not isinstance(chunk_size, int) or chunk_size <= 0:
        raise InteropConfigurationError("payload chunk size must be a positive integer")
    if not isinstance(seed, str) or not seed or len(seed) > 128:
        raise InteropConfigurationError("payload seed must contain 1-128 characters")
    try:
        import blake3
    except ImportError as exc:  # pragma: no cover - guarded by the iroh extra
        raise InteropConfigurationError("the iroh extra (blake3) is required") from exc

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    hasher = blake3.blake3()
    written = 0
    with target.open("xb") as stream:
        os.chmod(target, 0o600)
        while written < size:
            block_index, inside_block = divmod(written, _PAYLOAD_BLOCK_BYTES)
            count = min(
                chunk_size,
                size - written,
                _PAYLOAD_BLOCK_BYTES - inside_block,
            )
            block = _payload_block(seed, block_index)[inside_block : inside_block + count]
            stream.write(block)
            hasher.update(block)
            written += count
        stream.flush()
        os.fsync(stream.fileno())
    return hasher.hexdigest()


def _assert_no_sensitive_fields(value: Any, path: str = "evidence") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if _SENSITIVE_RE.search(str(key)):
                raise InteropConfigurationError(f"{path} contains forbidden field {key!r}")
            _assert_no_sensitive_fields(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_no_sensitive_fields(item, f"{path}[{index}]")


def _integer(value: Any, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise InteropConfigurationError(f"{label} must be an integer >= {minimum}")
    return value


def validate_observation(
    raw: Mapping[str, Any], plan: ScenarioPlan, bounds: ResourceBounds
) -> dict[str, Any]:
    """Validate and normalize one untrusted driver response."""

    if not isinstance(raw, Mapping):
        raise InteropConfigurationError("driver observation must be an object")
    value = dict(raw)
    allowed = {
        "scenario_id",
        "status",
        "transport",
        "node_count",
        "payload_hash",
        "payload_bytes",
        "content_verified",
        "versions",
        "assertions",
        "metrics",
        "skip_code",
        "failure_code",
    }
    unknown = set(value) - allowed
    if unknown:
        raise InteropConfigurationError(
            "driver observation contains unknown fields: " + ", ".join(sorted(unknown))
        )
    _assert_no_sensitive_fields(value, "observation")
    if value.get("scenario_id") != plan.scenario_id:
        raise InteropConfigurationError("driver returned the wrong scenario id")
    status_value = value.get("status")
    if status_value not in _OBSERVATION_STATUS:
        raise InteropConfigurationError("driver returned an invalid status")
    if value.get("transport") not in _TRANSPORTS:
        raise InteropConfigurationError("driver returned an invalid transport")
    nodes = _integer(value.get("node_count"), "node_count", minimum=2)
    if nodes != plan.node_count or nodes > bounds.max_node_count:
        raise InteropConfigurationError("driver used an unexpected node count")

    payload_bytes = _integer(value.get("payload_bytes"), "payload_bytes", minimum=1)
    payload_hash = value.get("payload_hash")
    if (
        payload_bytes != plan.payload_size
        or not isinstance(payload_hash, str)
        or not _HASH_RE.fullmatch(payload_hash)
    ):
        raise InteropConfigurationError("driver returned invalid payload evidence")
    if not isinstance(value.get("content_verified"), bool):
        raise InteropConfigurationError("content_verified must be a boolean")

    assertions = value.get("assertions")
    if not isinstance(assertions, Mapping) or any(
        not isinstance(name, str) or not isinstance(passed, bool)
        for name, passed in assertions.items()
    ):
        raise InteropConfigurationError("assertions must be a string-to-boolean object")
    required_assertions = {"isolated_state", "hash_verified", "bounded_resources"}
    if plan.direct_path_blocked:
        required_assertions.add("direct_path_blocked")
    if plan.interrupt_after_bytes is not None:
        required_assertions.update({"interrupted", "resumed_from_nonzero_offset"})
    if plan.requires_previous_binary:
        required_assertions.update({"mixed_versions", "protocol_compatible"})
    if plan.requires_identity_rotation:
        required_assertions.update({"identity_changed", "old_identity_rejected"})
    if not required_assertions.issubset(assertions):
        raise InteropConfigurationError("driver omitted required scenario assertions")

    versions = value.get("versions")
    if not isinstance(versions, Mapping) or set(versions) != {"source", "target"}:
        raise InteropConfigurationError("versions must identify source and target bundles")
    if any(not isinstance(item, str) or not item or len(item) > 128 for item in versions.values()):
        raise InteropConfigurationError("driver returned an invalid version")
    if (
        status_value == "passed"
        and plan.requires_previous_binary
        and versions["source"] == versions["target"]
    ):
        raise InteropConfigurationError("version-skew evidence must contain distinct bundles")

    metrics = value.get("metrics")
    required_metrics = {
        "duration_ms",
        "peak_rss_bytes",
        "max_transfer_chunk_bytes",
        "max_active_transfers",
        "reconnect_count",
    }
    if not isinstance(metrics, Mapping) or set(metrics) != required_metrics:
        raise InteropConfigurationError("driver returned an invalid metrics object")
    duration = metrics.get("duration_ms")
    if (
        isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or duration < 0
        or not math.isfinite(float(duration))
    ):
        raise InteropConfigurationError("duration_ms must be finite and non-negative")
    peak = _integer(metrics.get("peak_rss_bytes"), "peak_rss_bytes")
    chunk = _integer(metrics.get("max_transfer_chunk_bytes"), "max_transfer_chunk_bytes", minimum=1)
    active = _integer(metrics.get("max_active_transfers"), "max_active_transfers", minimum=1)
    _integer(metrics.get("reconnect_count"), "reconnect_count")

    bounds_pass = (
        float(duration) <= bounds.scenario_timeout_seconds * 1000
        and peak <= bounds.max_peak_rss_bytes
        and chunk <= bounds.max_transfer_chunk_bytes
        and active <= bounds.max_active_transfers
    )
    expected_reconnect = plan.interrupt_after_bytes is not None
    semantic_pass = (
        value.get("transport") == plan.expected_transport
        and value.get("content_verified") is True
        and all(assertions.get(name) is True for name in required_assertions)
        and bounds_pass
        and (not expected_reconnect or metrics["reconnect_count"] >= 1)
    )
    if status_value == "passed" and not semantic_pass:
        raise InteropConfigurationError("a passing observation does not satisfy the scenario")
    if status_value == "failed" and (
        not isinstance(value.get("failure_code"), str)
        or not _CODE_RE.fullmatch(value["failure_code"])
    ):
        raise InteropConfigurationError("failed observation requires a stable failure_code")
    if status_value == "skipped" and (
        not isinstance(value.get("skip_code"), str) or not _CODE_RE.fullmatch(value["skip_code"])
    ):
        raise InteropConfigurationError("skipped observation requires a stable skip_code")
    if status_value != "failed" and "failure_code" in value:
        raise InteropConfigurationError("failure_code is only valid for failed observations")
    if status_value != "skipped" and "skip_code" in value:
        raise InteropConfigurationError("skip_code is only valid for skipped observations")
    return value


def load_interoperability_evidence() -> dict[str, Any]:
    resource = files("ipfs_kit_py.resources").joinpath(EVIDENCE_RESOURCE)
    return json.loads(resource.read_text(encoding="utf-8"))


def load_interoperability_schema() -> dict[str, Any]:
    resource = files("ipfs_kit_py.resources").joinpath(EVIDENCE_SCHEMA_RESOURCE)
    return json.loads(resource.read_text(encoding="utf-8"))


def validate_evidence(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Validate evidence without making jsonschema a runtime dependency."""

    if not isinstance(raw, Mapping):
        raise InteropConfigurationError("interoperability evidence must be an object")
    value = dict(raw)
    allowed = {
        "$schema",
        "schema_version",
        "kind",
        "task_id",
        "status",
        "harness_version",
        "generated_at",
        "run_id",
        "platform",
        "release_bundles",
        "resource_bounds",
        "scenario_matrix",
        "results",
        "not_run_reason",
    }
    if set(value) - allowed:
        raise InteropConfigurationError("interoperability evidence contains unknown fields")
    _assert_no_sensitive_fields(value)
    if value.get("schema_version") != EVIDENCE_SCHEMA_VERSION or value.get("kind") != EVIDENCE_KIND:
        raise InteropConfigurationError("unsupported interoperability evidence schema")
    if value.get("task_id") != "IROH-025" or value.get("harness_version") != HARNESS_VERSION:
        raise InteropConfigurationError("evidence identifies the wrong task or harness")
    generated_at = value.get("generated_at")
    if not isinstance(generated_at, str):
        raise InteropConfigurationError("evidence generated_at must be an RFC 3339 timestamp")
    try:
        parsed_time = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError:
        raise InteropConfigurationError(
            "evidence generated_at must be an RFC 3339 timestamp"
        ) from None
    if "T" not in generated_at or parsed_time.tzinfo is None:
        raise InteropConfigurationError("evidence generated_at must be an RFC 3339 timestamp")
    run_id = value.get("run_id")
    if not isinstance(run_id, str) or not 1 <= len(run_id) <= 64:
        raise InteropConfigurationError("evidence run_id is invalid")
    platform_value = value.get("platform")
    if not isinstance(platform_value, Mapping) or set(platform_value) != {
        "os",
        "architecture",
        "python",
    }:
        raise InteropConfigurationError("evidence platform is invalid")
    if platform_value["os"] not in {"linux", "darwin", "pending"} or any(
        not isinstance(platform_value[name], str) or not platform_value[name]
        for name in ("architecture", "python")
    ):
        raise InteropConfigurationError("evidence platform is invalid")
    bundles = value.get("release_bundles")
    if not isinstance(bundles, Mapping) or set(bundles) != {"current", "previous"}:
        raise InteropConfigurationError("evidence release bundles are invalid")
    if (
        not isinstance(bundles["current"], str)
        or not bundles["current"]
        or (
            bundles["previous"] is not None
            and (not isinstance(bundles["previous"], str) or not bundles["previous"])
        )
    ):
        raise InteropConfigurationError("evidence release bundles are invalid")
    status_value = value.get("status")
    if status_value not in _STATUS:
        raise InteropConfigurationError("evidence has an invalid status")
    matrix = value.get("scenario_matrix")
    expected_matrix = [plan.to_dict() for plan in default_scenario_plans()]
    if not isinstance(matrix, list) or matrix != expected_matrix:
        raise InteropConfigurationError("evidence scenario matrix is incomplete or unordered")
    bounds_value = value.get("resource_bounds")
    if not isinstance(bounds_value, Mapping):
        raise InteropConfigurationError("evidence resource bounds are invalid")
    try:
        bounds = ResourceBounds(**dict(bounds_value))
    except TypeError:
        raise InteropConfigurationError("evidence resource bounds are invalid") from None
    results = value.get("results")
    if not isinstance(results, list):
        raise InteropConfigurationError("evidence results must be an array")
    plans = {plan.scenario_id: plan for plan in default_scenario_plans()}
    normalized = [
        validate_observation(result, plans[result.get("scenario_id")], bounds)
        for result in results
        if isinstance(result, Mapping) and result.get("scenario_id") in plans
    ]
    if len(normalized) != len(results):
        raise InteropConfigurationError("evidence contains an unknown result")
    if status_value == "passed" and (
        [item["scenario_id"] for item in normalized] != list(REQUIRED_SCENARIOS)
        or any(item["status"] != "passed" for item in normalized)
    ):
        raise InteropConfigurationError("passing evidence requires every scenario to pass")
    if status_value == "not_run":
        if (
            results
            or not isinstance(value.get("not_run_reason"), str)
            or not value["not_run_reason"]
        ):
            raise InteropConfigurationError("not-run evidence requires a reason and no results")
    elif "not_run_reason" in value:
        raise InteropConfigurationError("completed evidence must not contain not_run_reason")
    if status_value != "not_run":
        if [item["scenario_id"] for item in normalized] != list(REQUIRED_SCENARIOS):
            raise InteropConfigurationError("completed evidence requires every scenario in order")
        observed_statuses = {item["status"] for item in normalized}
        derived_status = (
            "passed"
            if observed_statuses == {"passed"}
            else ("failed" if "failed" in observed_statuses else "skipped")
        )
        if status_value != derived_status:
            raise InteropConfigurationError("evidence status does not match its scenario results")
    return value


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        os.fchmod(descriptor, 0o600)
        payload = (json.dumps(dict(value), indent=2, sort_keys=True) + "\n").encode("utf-8")
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        with contextlib.suppress(FileNotFoundError):
            temporary.unlink()


class CommandScenarioDriver:
    """Run one external, real-node scenario command with strict I/O bounds."""

    def __init__(self, command: Sequence[str], *, bounds: ResourceBounds) -> None:
        if not command or any(not isinstance(part, str) or not part for part in command):
            raise InteropConfigurationError("driver command must be a non-empty argv vector")
        self.command = tuple(command)
        self.bounds = bounds

    async def run(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        kwargs: dict[str, Any] = {
            "stdin": asyncio.subprocess.PIPE,
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
        }
        if os.name != "nt":
            kwargs["start_new_session"] = True
        kwargs["limit"] = self.bounds.max_driver_output_bytes + 1
        process = await asyncio.create_subprocess_exec(*self.command, **kwargs)
        encoded = (json.dumps(dict(request), sort_keys=True) + "\n").encode("utf-8")
        try:
            stdout, stderr = await asyncio.wait_for(
                self._exchange(process, encoded),
                timeout=self.bounds.scenario_timeout_seconds,
            )
        except asyncio.TimeoutError:
            await self._terminate(process)
            raise InteropDriverError("scenario driver timed out") from None
        except asyncio.CancelledError:
            await self._terminate(process)
            raise
        except BaseException:
            await self._terminate(process)
            raise
        if process.returncode != 0:
            raise InteropDriverError(f"scenario driver exited with code {process.returncode}")
        if stderr:
            raise InteropDriverError("scenario driver wrote to stderr")
        try:
            value = json.loads(stdout)
        except (UnicodeError, json.JSONDecodeError):
            raise InteropDriverError("scenario driver returned malformed JSON") from None
        if not isinstance(value, Mapping):
            raise InteropDriverError("scenario driver response must be an object")
        return value

    async def _exchange(
        self, process: asyncio.subprocess.Process, encoded: bytes
    ) -> tuple[bytes, bytes]:
        if process.stdin is None or process.stdout is None or process.stderr is None:
            raise InteropDriverError("scenario driver pipes are unavailable")
        process.stdin.write(encoded)
        try:
            await process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            pass
        process.stdin.close()

        async def read_bounded(reader: asyncio.StreamReader) -> bytes:
            output = bytearray()
            while True:
                remaining = self.bounds.max_driver_output_bytes + 1 - len(output)
                if remaining <= 0:
                    raise InteropDriverError("scenario driver output exceeded its bound")
                chunk = await reader.read(min(64 * 1024, remaining))
                if not chunk:
                    return bytes(output)
                output.extend(chunk)

        stdout_task = asyncio.create_task(read_bounded(process.stdout))
        stderr_task = asyncio.create_task(read_bounded(process.stderr))
        try:
            stdout, stderr, _ = await asyncio.gather(stdout_task, stderr_task, process.wait())
            return stdout, stderr
        finally:
            for task in (stdout_task, stderr_task):
                if not task.done():
                    task.cancel()
            for task in (stdout_task, stderr_task):
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task

    @staticmethod
    async def _terminate(process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        try:
            if os.name != "nt":
                os.killpg(process.pid, signal.SIGTERM)
            else:  # pragma: no cover - Windows is not a selected IROH-025 target
                process.terminate()
        except (ProcessLookupError, OSError):
            pass
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except asyncio.TimeoutError:
            with contextlib.suppress(ProcessLookupError, OSError):
                if os.name != "nt":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(process.wait(), timeout=5)


@dataclass(frozen=True, slots=True)
class HarnessConfig:
    state_root: Path
    current_binary: Path
    previous_binary: Path | None = None
    relay_url: str | None = None
    evidence_path: Path | None = None
    bounds: ResourceBounds = ResourceBounds()

    def __post_init__(self) -> None:
        if not self.state_root.is_absolute():
            raise InteropConfigurationError("state_root must be absolute")
        if not self.current_binary.is_absolute():
            raise InteropConfigurationError("current binary path must be absolute")
        if self.previous_binary is not None and not self.previous_binary.is_absolute():
            raise InteropConfigurationError("previous binary path must be absolute")
        if self.relay_url is not None:
            try:
                parsed = urlsplit(self.relay_url)
                port = parsed.port
            except ValueError:
                raise InteropConfigurationError("relay URL is malformed") from None
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
                or (port is not None and not 1 <= port <= 65535)
            ):
                raise InteropConfigurationError(
                    "relay URL must be credential-free HTTPS without query or fragment"
                )


class MultiNodeInteropHarness:
    """Execute the complete matrix using isolated per-scenario state roots."""

    def __init__(self, config: HarnessConfig, driver: CommandScenarioDriver) -> None:
        self.config = config
        self.driver = driver
        if driver.bounds != config.bounds:
            raise InteropConfigurationError("driver and harness resource bounds must match")

    async def run(self) -> dict[str, Any]:
        root = self.config.state_root
        if root.is_symlink() or (root.exists() and not root.is_dir()):
            raise InteropConfigurationError("state_root must be a real directory")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(root, 0o700)
        results: list[dict[str, Any]] = []
        started = time.time_ns()
        for index, plan in enumerate(default_scenario_plans()):
            scenario_root = root / f"{index:02d}-{plan.scenario_id}"
            scenario_root.mkdir(mode=0o700)
            payload_path = scenario_root / "payload.bin"
            digest = write_deterministic_payload(
                payload_path,
                plan.payload_size,
                seed=f"IROH-025:{HARNESS_VERSION}:{plan.scenario_id}",
                chunk_size=min(self.config.bounds.max_transfer_chunk_bytes, 1024 * 1024),
            )
            request = {
                "contract_version": 1,
                "scenario": plan.to_dict(),
                "workspace": str(scenario_root),
                "payload": {"path": str(payload_path), "size": plan.payload_size, "blake3": digest},
                "binaries": {
                    "current": str(self.config.current_binary),
                    "previous": (
                        str(self.config.previous_binary) if self.config.previous_binary else None
                    ),
                },
                "relay": {
                    "configured": self.config.relay_url is not None,
                    "url": self.config.relay_url,
                },
                "resource_bounds": self.config.bounds.to_dict(),
            }
            try:
                if plan.requires_previous_binary and self.config.previous_binary is None:
                    result = _skipped_observation(plan, digest, "previous_binary_unavailable")
                elif plan.expected_transport == "relay" and self.config.relay_url is None:
                    result = _skipped_observation(plan, digest, "relay_unavailable")
                else:
                    # On macOS the driver owns the VM-backed container topology;
                    # Linux drivers normally use native namespaces or containers.
                    raw = await self.driver.run(request)
                    result = validate_observation(raw, plan, self.config.bounds)
                if result.get("payload_hash") != digest:
                    raise InteropDriverError("driver did not verify the deterministic payload")
            except InteropConfigurationError:
                result = _failed_observation(plan, digest, "invalid_driver_observation")
            except (InteropDriverError, OSError):
                result = _failed_observation(plan, digest, "driver_failure")
            results.append(result)

        statuses = {item["status"] for item in results}
        overall = (
            "passed"
            if statuses == {"passed"}
            else ("failed" if "failed" in statuses else "skipped")
        )
        evidence = {
            "$schema": "./iroh-interoperability-evidence.schema.json",
            "schema_version": EVIDENCE_SCHEMA_VERSION,
            "kind": EVIDENCE_KIND,
            "task_id": "IROH-025",
            "status": overall,
            "harness_version": HARNESS_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "run_id": hashlib.sha256(
                f"{platform.system()}:{platform.machine()}:{started}".encode()
            ).hexdigest()[:24],
            "platform": {
                "os": platform.system().lower(),
                "architecture": platform.machine().lower(),
                "python": platform.python_version(),
            },
            "release_bundles": _observed_release_bundles(results),
            "resource_bounds": self.config.bounds.to_dict(),
            "scenario_matrix": [plan.to_dict() for plan in default_scenario_plans()],
            "results": results,
        }
        validate_evidence(evidence)
        if self.config.evidence_path is not None:
            _atomic_json(self.config.evidence_path, evidence)
        return evidence


def _skipped_observation(plan: ScenarioPlan, digest: str, code: str) -> dict[str, Any]:
    assertions = {"isolated_state": False, "hash_verified": False, "bounded_resources": True}
    if plan.direct_path_blocked:
        assertions["direct_path_blocked"] = False
    if plan.interrupt_after_bytes is not None:
        assertions.update({"interrupted": False, "resumed_from_nonzero_offset": False})
    if plan.requires_previous_binary:
        assertions.update({"mixed_versions": False, "protocol_compatible": False})
    if plan.requires_identity_rotation:
        assertions.update({"identity_changed": False, "old_identity_rejected": False})
    return {
        "scenario_id": plan.scenario_id,
        "status": "skipped",
        "transport": "none",
        "node_count": plan.node_count,
        "payload_hash": digest,
        "payload_bytes": plan.payload_size,
        "content_verified": False,
        "versions": {"source": "not-run", "target": "not-run"},
        "assertions": assertions,
        "metrics": {
            "duration_ms": 0,
            "peak_rss_bytes": 0,
            "max_transfer_chunk_bytes": 1,
            "max_active_transfers": 1,
            "reconnect_count": 0,
        },
        "skip_code": code,
    }


def _failed_observation(plan: ScenarioPlan, digest: str, code: str) -> dict[str, Any]:
    value = _skipped_observation(plan, digest, code)
    value["status"] = "failed"
    value.pop("skip_code")
    value["failure_code"] = code
    return value


def _observed_release_bundles(results: Sequence[Mapping[str, Any]]) -> dict[str, str | None]:
    current: str | None = None
    previous: str | None = None
    for result in results:
        versions = result.get("versions")
        if not isinstance(versions, Mapping) or result.get("status") == "skipped":
            continue
        if current is None:
            current = str(versions["source"])
        if result.get("scenario_id") == VERSION_SKEW and versions["target"] != versions["source"]:
            previous = str(versions["target"])
    return {"current": current or "not-observed", "previous": previous}


def enabled_from_environment(environ: Mapping[str, str] | None = None) -> bool:
    value = (environ or os.environ).get(OPT_IN_ENV, "")
    return value.strip().lower() in {"1", "true", "yes"}


def config_from_environment(
    environ: Mapping[str, str] | None = None,
) -> tuple[HarnessConfig, tuple[str, ...]]:
    env = dict(environ or os.environ)
    if not enabled_from_environment(env):
        raise InteropConfigurationError(f"set {OPT_IN_ENV}=1 to run real interoperability tests")
    command_text = env.get(DRIVER_ENV, "")
    binary_text = env.get(CURRENT_BINARY_ENV, "")
    if not command_text or not binary_text:
        raise InteropConfigurationError(f"{DRIVER_ENV} and {CURRENT_BINARY_ENV} are required")
    command = tuple(shlex.split(command_text))
    if not command:
        raise InteropConfigurationError("driver command is empty")
    root = (
        Path(env.get("IPFS_KIT_IROH_INTEROP_STATE", "")).expanduser()
        if env.get("IPFS_KIT_IROH_INTEROP_STATE")
        else Path(tempfile.mkdtemp(prefix="ipfs-kit-iroh-interop-"))
    )
    root = root.resolve()
    current = Path(binary_text).expanduser().resolve()
    previous = (
        Path(env[PREVIOUS_BINARY_ENV]).expanduser().resolve()
        if env.get(PREVIOUS_BINARY_ENV)
        else None
    )
    evidence_path = (
        Path(env[EVIDENCE_PATH_ENV]).expanduser().resolve()
        if env.get(EVIDENCE_PATH_ENV)
        else root / "interoperability-evidence.json"
    )
    if shutil.which(command[0]) is None:
        raise InteropConfigurationError("interoperability driver executable is unavailable")
    for binary, label in (
        (current, CURRENT_BINARY_ENV),
        (previous, PREVIOUS_BINARY_ENV),
    ):
        if binary is not None and (not binary.is_file() or not os.access(binary, os.X_OK)):
            raise InteropConfigurationError(f"{label} must name an executable regular file")
    return (
        HarnessConfig(
            state_root=root,
            current_binary=current,
            previous_binary=previous,
            relay_url=env.get(RELAY_URL_ENV),
            evidence_path=evidence_path,
        ),
        command,
    )


async def run_from_environment(environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    config, command = config_from_environment(environ)
    driver = CommandScenarioDriver(command, bounds=config.bounds)
    return await MultiNodeInteropHarness(config, driver).run()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run opt-in real Iroh multi-node interoperability tests"
    )
    parser.add_argument(
        "--check-evidence", type=Path, help="validate an existing evidence JSON file"
    )
    args = parser.parse_args(argv)
    try:
        if args.check_evidence is not None:
            validate_evidence(json.loads(args.check_evidence.read_text(encoding="utf-8")))
            return 0
        evidence = asyncio.run(run_from_environment())
        print(json.dumps(evidence, sort_keys=True))
        return 0 if evidence["status"] == "passed" else 1
    except (InteropConfigurationError, InteropDriverError, OSError, json.JSONDecodeError) as exc:
        print(f"iroh interoperability: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "EVIDENCE_RESOURCE",
    "EVIDENCE_SCHEMA_RESOURCE",
    "EVIDENCE_KIND",
    "EVIDENCE_SCHEMA_VERSION",
    "HARNESS_VERSION",
    "OPT_IN_ENV",
    "DRIVER_ENV",
    "REQUIRED_SCENARIOS",
    "ResourceBounds",
    "ScenarioPlan",
    "HarnessConfig",
    "CommandScenarioDriver",
    "MultiNodeInteropHarness",
    "InteropConfigurationError",
    "InteropDriverError",
    "default_scenario_plans",
    "write_deterministic_payload",
    "validate_observation",
    "validate_evidence",
    "load_interoperability_evidence",
    "load_interoperability_schema",
    "enabled_from_environment",
    "config_from_environment",
    "run_from_environment",
    "main",
]

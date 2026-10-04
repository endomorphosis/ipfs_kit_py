"""Safe health receipts and bounded-cardinality metrics for Iroh instances.

The sidecar is deliberately treated as an untrusted diagnostics source. Only
the documented scalar fields in this module cross the boundary; arbitrary
object keys, peer identities, paths, tickets, credentials, and error strings
are never copied into a receipt or metric label.
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
import math
import os
import shutil
import stat
import tempfile
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .client import IrohRuntimeClient
from .config import FILE_MODE, IrohServiceConfig, ensure_state_layout, validate_instance_name

HEALTH_SCHEMA_VERSION = 1
HEALTH_KIND = "ipfs-kit-iroh-health"
METRICS_KIND = "ipfs-kit-iroh-metrics"
UNKNOWN_VERSION = "unknown"

_CONNECTIVITY_STATES = frozenset({"unknown", "disabled", "connected", "connecting", "disconnected"})
_GC_STATES = frozenset({"unknown", "disabled", "idle", "running", "failed"})
_SERVICE_STATES = frozenset(
    {"unknown", "stopped", "starting", "running", "stopping", "crashed", "foreign", "stale"}
)
_PUBLIC_IDENTIFIER_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.+_-"
)
_VERSION_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.+_-")


def _utc_now(clock: Callable[[], float] = time.time) -> str:
    return datetime.fromtimestamp(clock(), timezone.utc).isoformat().replace("+00:00", "Z")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first(source: Mapping[str, Any], *paths: str, default: Any = None) -> Any:
    """Return the first present value, supporting dotted paths."""

    for path in paths:
        value: Any = source
        for part in path.split("."):
            if not isinstance(value, Mapping) or part not in value:
                break
            value = value[part]
        else:
            return value
    return default


def _boolean(value: Any, default: bool = False) -> bool:
    return value if isinstance(value, bool) else bool(default)


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        value = default
    result = float(value)
    if not math.isfinite(result) or result < 0:
        return max(0.0, float(default)) if math.isfinite(float(default)) else 0.0
    return result


def _integer(value: Any, default: int = 0) -> int:
    return int(_number(value, float(default)))


def _enum(value: Any, allowed: frozenset[str], default: str = "unknown") -> str:
    if isinstance(value, str):
        result = value.lower()
        return result if result in allowed else default
    if isinstance(value, bool) and allowed is _CONNECTIVITY_STATES:
        return "connected" if value else "disconnected"
    return default


def _public_identifier(value: Any) -> str | None:
    """Accept a public node ID while rejecting paths, URLs, and large data."""

    if (
        not isinstance(value, str)
        or not value
        or len(value) > 128
        or any(char.isspace() for char in value)
        or any(char not in _PUBLIC_IDENTIFIER_CHARS for char in value)
    ):
        return None
    return value


def _version(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 64
        or not all(char in _VERSION_CHARS for char in value)
    ):
        return UNKNOWN_VERSION
    return value


def _directory_size(path: Path) -> int:
    """Count regular files without following directory or file symlinks."""

    total = 0
    if path.is_symlink():
        return total
    for root, directories, files in os.walk(path, followlinks=False):
        directories[:] = [name for name in directories if not (Path(root) / name).is_symlink()]
        for name in files:
            candidate = Path(root) / name
            if candidate.is_symlink():
                continue
            with contextlib.suppress(OSError):
                metadata = candidate.stat(follow_symlinks=False)
                if stat.S_ISREG(metadata.st_mode):
                    total += metadata.st_size
    return total


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    """Atomically write a durable owner-only JSON document."""

    descriptor: int | None = None
    temporary: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(name)
        os.fchmod(descriptor, FILE_MODE)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            descriptor = None
            json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
        path.chmod(FILE_MODE)
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        directory = os.open(path.parent, flags)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary is not None:
            with contextlib.suppress(FileNotFoundError):
                temporary.unlink()


@dataclass(frozen=True, slots=True)
class IrohHealthReceipt:
    """Validated, JSON-serializable public diagnostic snapshot."""

    value: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(self.value, allow_nan=False))

    @property
    def live(self) -> bool:
        return bool(self.value["liveness"]["live"])

    @property
    def ready(self) -> bool:
        return bool(self.value["readiness"]["ready"])


def normalize_health(
    raw: Mapping[str, Any] | None,
    *,
    instance: str,
    live: bool,
    ready: bool,
    service_state: str = "unknown",
    storage_used_bytes: int = 0,
    storage_capacity_bytes: int = 0,
    observed_at: str | None = None,
    probe_latency_ms: float = 0.0,
) -> IrohHealthReceipt:
    """Build the schema-v1 allowlisted receipt from untrusted sidecar data."""

    source = _mapping(raw)
    try:
        safe_instance = validate_instance_name(instance)
    except Exception:
        safe_instance = "invalid"

    transfers = _mapping(_first(source, "transfers", "transfer", default={}))
    failures = _mapping(_first(source, "failures", default={}))
    storage = _mapping(_first(source, "storage", default={}))
    connectivity = _mapping(_first(source, "connectivity", "network", default={}))
    gc = _mapping(_first(source, "gc", "garbage_collection", default={}))
    manifests = _mapping(_first(source, "manifests", "manifest", default={}))
    latency = _mapping(_first(source, "latency", default={}))

    node_id = _public_identifier(_first(source, "node_id", "node.id", "id"))
    version = _version(_first(source, "version", "node.version", "sidecar_version"))
    uptime = _number(_first(source, "uptime_seconds", "uptime", "node.uptime_seconds"))
    used = _integer(_first(storage, "used_bytes", "bytes_used"), storage_used_bytes)
    capacity = _integer(_first(storage, "capacity_bytes", "limit_bytes"), storage_capacity_bytes)
    peers = _integer(_first(source, "peers_connected", "peer_count", "peers.connected", default=0))
    direct = _enum(
        _first(connectivity, "direct", "direct_state", "direct_connected"),
        _CONNECTIVITY_STATES,
    )
    relay = _enum(
        _first(connectivity, "relay", "relay_state", "relay_connected"),
        _CONNECTIVITY_STATES,
    )

    receipt = {
        "schema_version": HEALTH_SCHEMA_VERSION,
        "kind": HEALTH_KIND,
        "observed_at": observed_at or _utc_now(),
        "instance": safe_instance,
        "liveness": {
            "live": bool(live),
            "state": service_state if service_state in _SERVICE_STATES else "unknown",
        },
        "readiness": {
            "ready": bool(ready),
            "probe_latency_ms": _number(probe_latency_ms),
        },
        "node": {"id": node_id, "version": version, "uptime_seconds": uptime},
        "connectivity": {
            "direct": direct,
            "relay": relay,
            "peers_connected": peers,
        },
        "storage": {"used_bytes": used, "capacity_bytes": capacity},
        "transfers": {
            "active": _integer(_first(transfers, "active", "active_count")),
            "completed_total": _integer(_first(transfers, "completed_total", "completed", "count")),
            "failed_total": _integer(_first(transfers, "failed_total", "failed")),
            "sent_bytes_total": _integer(
                _first(transfers, "sent_bytes_total", "bytes_sent", "upload_bytes")
            ),
            "received_bytes_total": _integer(
                _first(
                    transfers,
                    "received_bytes_total",
                    "bytes_received",
                    "download_bytes",
                )
            ),
        },
        "failures": {
            "total": _integer(
                _first(
                    failures,
                    "total",
                    "count",
                    default=_first(source, "failures_total", default=0),
                )
            )
        },
        "latency": {
            "rpc_ms": _number(_first(latency, "rpc_ms", "request_ms", default=probe_latency_ms)),
            "transfer_ms": _number(_first(latency, "transfer_ms", "average_transfer_ms")),
        },
        "manifests": {
            "conflicts_total": _integer(
                _first(
                    manifests,
                    "conflicts_total",
                    "conflicts",
                    default=_first(source, "manifest_conflicts", default=0),
                )
            )
        },
        "gc": {
            "state": _enum(_first(gc, "state", "status"), _GC_STATES),
            "runs_total": _integer(_first(gc, "runs_total", "runs")),
            "reclaimed_bytes_total": _integer(
                _first(gc, "reclaimed_bytes_total", "reclaimed_bytes")
            ),
        },
    }
    return IrohHealthReceipt(receipt)


class IrohObservability:
    """Collect and persist safe diagnostics for one configured instance."""

    def __init__(
        self,
        config: IrohServiceConfig,
        *,
        service: Any | None = None,
        client: Any | None = None,
        client_factory: Callable[..., Any] = IrohRuntimeClient,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not isinstance(config, IrohServiceConfig):
            raise TypeError("config must be an IrohServiceConfig")
        self.config = config
        self.service = service
        self.client = client
        self.client_factory = client_factory
        self.clock = clock

    async def _service_status(self) -> Mapping[str, Any]:
        if self.service is None:
            return {}
        status = self.service.status()
        if inspect.isawaitable(status):
            status = await status
        return _mapping(status)

    async def _sidecar_diagnostics(self, client: Any) -> Mapping[str, Any]:
        diagnostic = getattr(client, "diagnostics", None)
        if diagnostic is not None:
            result = diagnostic()
        else:
            health = getattr(client, "health", None)
            if health is not None:
                result = health()
            else:
                result = client.request("system.diagnostics", require_negotiation=False)
        if inspect.isawaitable(result):
            result = await result
        return _mapping(result)

    async def collect(self, *, persist: bool = True) -> IrohHealthReceipt:
        status = await self._service_status()
        state_value = status.get("state", status.get("status", "unknown"))
        state = state_value if isinstance(state_value, str) else "unknown"
        live = _boolean(status.get("running"), state == "running")
        ready = _boolean(status.get("ready"), False)
        raw: Mapping[str, Any] = {}
        started = time.monotonic()
        client = self.client
        owns_client = client is None

        if client is None:
            try:
                client = self.client_factory(
                    endpoint=self.config.layout.rpc_socket_path, timeout=5.0
                )
            except TypeError:
                client = self.client_factory(endpoint=self.config.layout.rpc_socket_path)

        try:
            raw = await self._sidecar_diagnostics(client)
            live = _boolean(
                _first(raw, "live", "alive", "healthy"),
                True if not status else live,
            )
            ready = _boolean(_first(raw, "ready", "readiness.ready"), ready)
        except Exception:
            # Never include exception text: transports often embed paths,
            # peer IDs, request payloads, or credentials in their errors.
            ready = False
            if not status:
                live = False
        finally:
            if owns_client:
                close = getattr(client, "close", None)
                if close is not None:
                    with contextlib.suppress(Exception):
                        result = close()
                        if inspect.isawaitable(result):
                            await result

        elapsed_ms = (time.monotonic() - started) * 1000.0
        used = await asyncio.to_thread(_directory_size, self.config.layout.data_dir)
        try:
            capacity_path = (
                self.config.layout.data_dir
                if self.config.layout.data_dir.exists()
                else self.config.layout.root.parent
            )
            disk_capacity = shutil.disk_usage(capacity_path).total
        except OSError:
            disk_capacity = self.config.resources.max_storage_bytes
        capacity = min(disk_capacity, self.config.resources.max_storage_bytes)

        receipt = normalize_health(
            raw,
            instance=self.config.instance,
            live=live,
            ready=ready,
            service_state=state,
            storage_used_bytes=used,
            storage_capacity_bytes=capacity,
            observed_at=_utc_now(self.clock),
            probe_latency_ms=elapsed_ms,
        )
        if persist:
            ensure_state_layout(self.config)
            _atomic_json(self.config.layout.health_receipt_path, receipt.to_dict())
        return receipt

    async def diagnostics(self, *, persist: bool = True) -> dict[str, Any]:
        return (await self.collect(persist=persist)).to_dict()

    async def metrics(self, *, persist: bool = True) -> dict[str, Any]:
        return metrics_from_receipt(await self.collect(persist=persist))

    async def prometheus(self, *, persist: bool = True) -> str:
        return prometheus_from_receipt(await self.collect(persist=persist))


def metrics_from_receipt(
    receipt: IrohHealthReceipt | Mapping[str, Any],
) -> dict[str, Any]:
    """Convert a receipt to fixed-name, bounded-label metric samples."""

    value = receipt.value if isinstance(receipt, IrohHealthReceipt) else _mapping(receipt)
    try:
        instance = validate_instance_name(value.get("instance"))
    except Exception:
        instance = "invalid"
    label = {"instance": instance}
    connectivity = _mapping(value.get("connectivity"))
    transfers = _mapping(value.get("transfers"))

    def sample(
        name: str, metric_type: str, sample_labels: Mapping[str, str], number: int | float
    ) -> dict[str, Any]:
        return {
            "name": name,
            "type": metric_type,
            "labels": dict(sample_labels),
            "value": number,
        }

    samples = [
        sample("ipfs_kit_iroh_live", "gauge", label, int(_boolean(_first(value, "liveness.live")))),
        sample(
            "ipfs_kit_iroh_ready", "gauge", label, int(_boolean(_first(value, "readiness.ready")))
        ),
        sample(
            "ipfs_kit_iroh_uptime_seconds",
            "gauge",
            label,
            _number(_first(value, "node.uptime_seconds")),
        ),
        sample(
            "ipfs_kit_iroh_peers_connected",
            "gauge",
            label,
            _integer(connectivity.get("peers_connected")),
        ),
        sample(
            "ipfs_kit_iroh_connectivity",
            "gauge",
            {**label, "path": "direct"},
            int(connectivity.get("direct") == "connected"),
        ),
        sample(
            "ipfs_kit_iroh_connectivity",
            "gauge",
            {**label, "path": "relay"},
            int(connectivity.get("relay") == "connected"),
        ),
        sample(
            "ipfs_kit_iroh_storage_used_bytes",
            "gauge",
            label,
            _integer(_first(value, "storage.used_bytes")),
        ),
        sample(
            "ipfs_kit_iroh_storage_capacity_bytes",
            "gauge",
            label,
            _integer(_first(value, "storage.capacity_bytes")),
        ),
        sample("ipfs_kit_iroh_transfers_active", "gauge", label, _integer(transfers.get("active"))),
        sample(
            "ipfs_kit_iroh_transfers_total",
            "counter",
            {**label, "result": "completed"},
            _integer(transfers.get("completed_total")),
        ),
        sample(
            "ipfs_kit_iroh_transfers_total",
            "counter",
            {**label, "result": "failed"},
            _integer(transfers.get("failed_total")),
        ),
        sample(
            "ipfs_kit_iroh_transfer_bytes_total",
            "counter",
            {**label, "direction": "sent"},
            _integer(transfers.get("sent_bytes_total")),
        ),
        sample(
            "ipfs_kit_iroh_transfer_bytes_total",
            "counter",
            {**label, "direction": "received"},
            _integer(transfers.get("received_bytes_total")),
        ),
        sample(
            "ipfs_kit_iroh_failures_total",
            "counter",
            label,
            _integer(_first(value, "failures.total")),
        ),
        sample(
            "ipfs_kit_iroh_rpc_latency_seconds",
            "gauge",
            label,
            _number(_first(value, "latency.rpc_ms")) / 1000.0,
        ),
        sample(
            "ipfs_kit_iroh_transfer_latency_seconds",
            "gauge",
            label,
            _number(_first(value, "latency.transfer_ms")) / 1000.0,
        ),
        sample(
            "ipfs_kit_iroh_manifest_conflicts_total",
            "counter",
            label,
            _integer(_first(value, "manifests.conflicts_total")),
        ),
        sample(
            "ipfs_kit_iroh_gc_running", "gauge", label, int(_first(value, "gc.state") == "running")
        ),
        sample(
            "ipfs_kit_iroh_gc_runs_total",
            "counter",
            label,
            _integer(_first(value, "gc.runs_total")),
        ),
        sample(
            "ipfs_kit_iroh_gc_reclaimed_bytes_total",
            "counter",
            label,
            _integer(_first(value, "gc.reclaimed_bytes_total")),
        ),
    ]
    return {"schema_version": HEALTH_SCHEMA_VERSION, "kind": METRICS_KIND, "samples": samples}


def _prometheus_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def prometheus_from_receipt(receipt: IrohHealthReceipt | Mapping[str, Any]) -> str:
    """Render deterministic Prometheus exposition text."""

    metrics = metrics_from_receipt(receipt)
    lines: list[str] = []
    emitted: set[str] = set()
    for sample_value in metrics["samples"]:
        name = sample_value["name"]
        if name not in emitted:
            lines.extend(
                [
                    f"# HELP {name} IPFS Kit Iroh operational metric.",
                    f"# TYPE {name} {sample_value['type']}",
                ]
            )
            emitted.add(name)
        labels = ",".join(
            f'{key}="{_prometheus_escape(str(value))}"'
            for key, value in sorted(sample_value["labels"].items())
        )
        number = sample_value["value"]
        formatted = f"{number:g}" if isinstance(number, float) else str(number)
        lines.append(f"{name}{{{labels}}} {formatted}")
    return "\n".join(lines) + "\n"


async def collect_health(
    config: IrohServiceConfig,
    *,
    service: Any | None = None,
    client: Any | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Convenience operation for integrations which do not retain a collector."""

    return await IrohObservability(config, service=service, client=client).diagnostics(
        persist=persist
    )


# Compatibility names retained for integrations developed against the plan.
HealthReceipt = IrohHealthReceipt
Observability = IrohObservability
IrohHealthMonitor = IrohObservability
collect_metrics = metrics_from_receipt
render_prometheus = prometheus_from_receipt

__all__ = [
    "HEALTH_KIND",
    "HEALTH_SCHEMA_VERSION",
    "HealthReceipt",
    "IrohHealthReceipt",
    "IrohHealthMonitor",
    "IrohObservability",
    "Observability",
    "collect_health",
    "collect_metrics",
    "metrics_from_receipt",
    "normalize_health",
    "prometheus_from_receipt",
    "render_prometheus",
]

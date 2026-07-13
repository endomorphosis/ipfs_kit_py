from __future__ import annotations

import json
import os

import pytest

from ipfs_kit_py.iroh import (
    HEALTH_KIND,
    IrohObservability,
    IrohServiceConfig,
    metrics_from_receipt,
    normalize_health,
    prometheus_from_receipt,
)
from ipfs_kit_py.mcp.servers.iroh_mcp_tools import handle_iroh_diagnostics

SENSITIVE_VALUES = (
    "secret-node-key-material",
    "blob-ticket-private-value",
    "/private/alice/document.txt",
    "peer-sensitive-identity",
)


def diagnostic_payload():
    return {
        "healthy": True,
        "ready": False,
        "node": {"id": "publicnodeid123", "version": "1.0.2", "uptime_seconds": 42.5},
        "network": {"direct_connected": True, "relay": "connecting"},
        "peers": {"connected": 4, "ids": [SENSITIVE_VALUES[3]]},
        "storage": {"used_bytes": 1024, "capacity_bytes": 4096, "path": SENSITIVE_VALUES[2]},
        "transfers": {
            "active": 2,
            "completed": 8,
            "failed": 1,
            "bytes_sent": 123,
            "bytes_received": 456,
            "ticket": SENSITIVE_VALUES[1],
        },
        "failures": {"total": 3, "last_error": SENSITIVE_VALUES[3]},
        "latency": {"rpc_ms": 5.5, "transfer_ms": 7},
        "manifest": {"conflicts": 2, "path": SENSITIVE_VALUES[2]},
        "gc": {"state": "running", "runs": 9, "reclaimed_bytes": 88},
        "private_key": SENSITIVE_VALUES[0],
    }


def test_health_receipt_reports_required_operational_fields_without_sensitive_data():
    receipt = normalize_health(
        diagnostic_payload(),
        instance="main",
        live=True,
        ready=False,
        service_state="running",
        observed_at="2026-07-12T00:00:00Z",
    ).to_dict()
    assert receipt["kind"] == HEALTH_KIND
    assert receipt["liveness"] == {"live": True, "state": "running"}
    assert receipt["readiness"]["ready"] is False
    assert receipt["node"] == {"id": "publicnodeid123", "version": "1.0.2", "uptime_seconds": 42.5}
    assert receipt["connectivity"] == {
        "direct": "connected",
        "relay": "connecting",
        "peers_connected": 4,
    }
    assert receipt["transfers"]["sent_bytes_total"] == 123
    assert receipt["failures"]["total"] == 3
    assert receipt["manifests"]["conflicts_total"] == 2
    assert receipt["gc"]["state"] == "running"
    encoded = json.dumps(receipt)
    assert all(value not in encoded for value in SENSITIVE_VALUES)


def test_metrics_have_only_bounded_labels_and_prometheus_is_deterministic():
    receipt = normalize_health(
        diagnostic_payload(), instance="main", live=True, ready=False, observed_at="x"
    )
    metrics = metrics_from_receipt(receipt)
    allowed = {"instance", "result", "direction", "path"}
    allowed_values = {"main", "completed", "failed", "sent", "received", "direct", "relay"}
    for sample in metrics["samples"]:
        assert set(sample["labels"]) <= allowed
        assert set(sample["labels"].values()) <= allowed_values
    output = prometheus_from_receipt(receipt)
    assert 'ipfs_kit_iroh_connectivity{instance="main",path="direct"} 1' in output
    assert all(value not in output for value in SENSITIVE_VALUES)


@pytest.mark.asyncio
async def test_collector_persists_private_atomic_receipt(tmp_path):
    class Client:
        async def diagnostics(self):
            return diagnostic_payload()

    config = IrohServiceConfig.default("main", state_root=tmp_path, enabled=True)
    observer = IrohObservability(config, client=Client(), clock=lambda: 0)
    receipt = await observer.collect()
    persisted = json.loads(config.layout.health_receipt_path.read_text())
    assert persisted == receipt.to_dict()
    if os.name == "posix":
        assert config.layout.health_receipt_path.stat().st_mode & 0o777 == 0o600


@pytest.mark.asyncio
async def test_unreachable_sidecar_produces_live_false_ready_false_receipt(tmp_path):
    class Client:
        async def diagnostics(self):
            raise RuntimeError(SENSITIVE_VALUES[0])

    config = IrohServiceConfig.default("offline", state_root=tmp_path, enabled=True)
    result = await IrohObservability(config, client=Client()).diagnostics(persist=False)
    assert result["liveness"]["live"] is False
    assert result["readiness"]["ready"] is False
    assert SENSITIVE_VALUES[0] not in json.dumps(result)


@pytest.mark.asyncio
async def test_mcp_operation_returns_same_safe_contract(tmp_path):
    class Observer:
        def __init__(self, config):
            self.config = config

        async def diagnostics(self, *, persist=True):
            return normalize_health(
                diagnostic_payload(), instance=self.config.instance, live=True, ready=False
            ).to_dict()

    result = await handle_iroh_diagnostics(
        {"instance": "main", "persist": False},
        observability_factory=Observer,
        state_root=str(tmp_path),
    )
    assert result["success"] is True
    assert result["diagnostics"]["readiness"]["ready"] is False
    assert all(value not in json.dumps(result) for value in SENSITIVE_VALUES)


@pytest.mark.asyncio
async def test_mcp_rejects_unknown_arguments_without_echoing_them():
    result = await handle_iroh_diagnostics({"ticket": SENSITIVE_VALUES[1]})
    assert result["code"] == "invalid_arguments"
    assert SENSITIVE_VALUES[1] not in json.dumps(result)

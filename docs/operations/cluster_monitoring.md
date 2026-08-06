# Cluster monitoring (operations)

| Field | Value |
|---|---|
| Document class | Operator runbook (current-operations) |
| Status | active |
| Last verified | 2026-08-04 |
| Owner / task | KDOC-036 |
| Goal id | KDOC-G042 |
| Authority | Monitoring helpers **observe** cluster-related surfaces; they do **not** select a production control plane. [ADR-0008](../architecture/decisions/0008-cluster-control-plane-authority.md) remains **Proposed** (**U-08**). |
| Companion ops | [cluster_management.md](cluster_management.md), [cluster_state.md](cluster_state.md) |

This runbook covers **health checks, metrics collection, alerts, automated recovery actions, and dashboards** for kit cluster-related modules. It tags every API with **implementation family** and **prerequisites**. Unresolved multi-node authority is never converted into a production recommendation.

---

## 1. Two monitoring stacks (do not conflate)

Family A alone has **two** monitoring implementations with different constructors and wiring.

| Stack | Modules | Classes | How it is reached | Status |
|---|---|---|---|---|
| **A-package monitoring** | `ipfs_kit_py/cluster/monitoring.py` | `MetricsCollector`, `ClusterMonitor` | Imported by `ipfs_kit` when `enable_monitoring=True` (`HAS_MONITORING`) | candidate; also pulled into package `ClusterManager` composition (**broken** until §3 management mismatches fixed) |
| **A-toplevel monitoring** | `ipfs_kit_py/cluster_monitoring.py` | `ClusterMonitoring`, `ClusterDashboard` | Direct construction with an `ipfs_kit` instance; examples under `examples/cluster_monitoring_example.py` | candidate / experimental |
| **Observability export** | `prometheus_exporter.py` + ops guides | Prometheus metrics HTTP | Orthogonal metrics pipeline | production-oriented for **process** metrics, not multi-node control-plane authority |
| **Family B health** | Kubo cluster wrappers / unit health tests | Service status, API health | External process status | wrapper |
| **Family C health** | MCP++ `daemon_health` index | Expiring health artifacts by peer DID | DurableCoordinationStore domain | domain-scoped |

Architecture summary: [CLUSTER_COORDINATION.md §7](../architecture/CLUSTER_COORDINATION.md). Process metrics narrative: [observability.md](observability.md), [performance_metrics.md](performance_metrics.md).

**Log-message drift:** `ipfs_kit` may log “make sure cluster_monitoring.py is available” when package monitoring imports fail. The enable flag actually imports **`cluster.monitoring`**. Treat the log string as imprecise.

---

## 2. Prerequisites

### 2.1 Package monitoring (`MetricsCollector` / `ClusterMonitor`)

| Prerequisite | Why |
|---|---|
| Importable `ipfs_kit_py.cluster.monitoring` | `HAS_MONITORING` gate in `ipfs_kit` |
| `node_id` for collector | Constructor requires it |
| Optional `metrics_dir` | Persist time-series when set |
| Realistic collection interval | Default 60s class default |
| **Not** package `ClusterManager` construction | Manager still fails MetricsCollector kwargs mismatch when composed via package façade |

`MetricsCollector.__init__(node_id, metrics_dir=None, collection_interval=60, retention_days=7)` — **no** `role` parameter. Package manager call sites that pass `role=` raise `TypeError` (rank-1 mismatch evidence).

### 2.2 Top-level monitoring (`ClusterMonitoring` / `ClusterDashboard`)

| Prerequisite | Why |
|---|---|
| Live `ipfs_kit` instance reference | Constructor binds to kit metadata/config |
| Role in `master` or `worker` for auto-start | Leecher does not auto-start collection thread |
| `psutil` | Local resource gauges |
| Optional kit IPFS / cluster clients | GC and remote recovery actions need those hooks |
| Metadata config under `config.Monitoring.*` | Thresholds, intervals, history sizes |

### 2.3 Prometheus / Grafana path

| Prerequisite | Why |
|---|---|
| Exporter dependencies and bind address | Scrapable `/metrics` (or configured port) |
| Prometheus scrape config + Grafana | Visualization |
| Understanding of **process** vs **cluster control plane** | Exporter does not resolve U-08 |

### 2.4 Family B / C

| Family | Prerequisites |
|---|---|
| B | Running cluster service; kit wrappers for status; network to API |
| C | Coordination store directory; MCP++ runtime |

---

## 3. Operational API catalog (family-tagged)

### 3.1 Kit enablement

| API / flag | Family | Prerequisites | Status | Notes |
|---|---|---|---|---|
| `enable_monitoring=True` on `ipfs_kit` | A-package monitoring | `MetricsCollector` + `ClusterMonitor` import | candidate | `_setup_monitoring` wires package classes |
| Package `ClusterManager` embedding monitor | A-package composition | **Blocked** by constructor kwargs | **broken-until-repair** | Do not recommend as production enablement |

### 3.2 `MetricsCollector` (A-package)

| API | Family | Prerequisites | Status |
|---|---|---|---|
| `MetricsCollector(node_id, metrics_dir=…, collection_interval=…, retention_days=…)` | A-package | Valid node id | candidate |
| Time-series buffers / historical maps | A-package | Started collection path | candidate |
| Optional directory persistence | A-package | Writable `metrics_dir` | candidate |

### 3.3 `ClusterMonitor` (A-package)

| API (concept) | Family | Prerequisites | Status |
|---|---|---|---|
| Periodic checks + alert callback | A-package | Collector + membership hooks when provided | candidate |
| Membership-change hooks from package manager | A-package | Manager composition working | **blocked** while façade broken |

### 3.4 `ClusterMonitoring` (A-toplevel)

| API | Family | Prerequisites | Status |
|---|---|---|---|
| `ClusterMonitoring(ipfs_kit_instance)` | A-toplevel | Kit with `metadata` | candidate |
| `start_monitoring()` / `stop_monitoring()` | A-toplevel | Threading available | candidate |
| `collect_cluster_metrics()` | A-toplevel | Local and/or remote collection paths | candidate |
| `get_latest_metrics()` | A-toplevel | At least one successful collect | candidate |
| `check_alert_thresholds(metrics_data)` | A-toplevel | Threshold config | candidate |
| `process_alerts(alerts)` | A-toplevel | Alert list | candidate |
| `_execute_recovery_action` / pending queue | A-toplevel | Action type supported | experimental automation |
| `aggregate_metrics(time_range, interval)` | A-toplevel | Historical metrics retained | candidate |
| `export_metrics_json` / `export_metrics_csv` | A-toplevel | Aggregation succeeds | candidate |
| `validate_cluster_config` / `distribute_cluster_config` | A-toplevel | Config dict; peer list when distributing | experimental |

### 3.5 `ClusterDashboard` (A-toplevel)

| API | Family | Prerequisites | Status |
|---|---|---|---|
| `ClusterDashboard(ipfs_kit_instance, monitoring_instance=None)` | A-toplevel | Kit; optional existing monitor | candidate |
| `start_dashboard()` / `stop_dashboard()` | A-toplevel | Dashboard enabled in config | candidate |
| `generate_html_dashboard()` | A-toplevel | Metrics available preferred | candidate |

### 3.6 Adjacent status APIs

| API | Family | Prerequisites | Status |
|---|---|---|---|
| `kit.get_cluster_status()` | A façade | Manager attached | candidate / may fail if manager missing |
| MCP `cluster_status` | Adjacent | MCP + kit | candidate thin tool |
| Family B service status | B | Binaries running | wrapper |
| Family C daemon_health artifacts | C | Coordination store | domain-scoped |

---

## 4. Metrics collected (A-toplevel focus)

`ClusterMonitoring.collect_cluster_metrics` / `_collect_local_metrics` gather (intent):

| Category | Examples |
|---|---|
| System resources | CPU %, memory %, disk %, via `psutil` |
| IPFS-oriented | Repo/peer/pin queue style fields when kit clients expose them |
| Cluster-oriented | Node maps by id, role-sensitive fields when available |
| History | In-memory list capped by `MaxMetricsHistory` (default 1440 ≈ 24h at 1m) |

**Caveats:**

- Multi-node collection depends on reachable peers and kit APIs—not a guaranteed cluster-wide timeseries DB.
- Package `MetricsCollector` keeps separate deques/maps; do not assume identical field names across stacks.
- Prometheus exporter metrics (`ipfs_*` series in [observability.md](observability.md)) are a **different pipeline** unless explicitly bridged.

---

## 5. Configuration (A-toplevel)

Configuration is read from `ipfs_kit.metadata["config"]` with path keys under `Monitoring` (and dashboard-related keys where used).

| Key path | Default (code) | Meaning |
|---|---|---|
| `Monitoring.Enabled` | `True` | Allow monitoring subsystem |
| `Monitoring.MetricsInterval` | `"60s"` | Collection period (supports `s`/`m`/`h` suffixes) |
| `Monitoring.MaxMetricsHistory` | `1440` | In-memory metric samples retained |
| `Monitoring.MaxAlertHistory` | `1000` | Alert history cap |
| `Monitoring.MaxActionHistory` | `100` | Completed recovery actions retained |
| `Monitoring.AlertThresholds.DiskSpace` | `90` | Disk usage % |
| `Monitoring.AlertThresholds.MemoryUsage` | `85` | Memory usage % |
| `Monitoring.AlertThresholds.CpuUsage` | `90` | CPU usage % |
| `Monitoring.AlertThresholds.PinQueueLength` | `100` | Pins queued |
| `Monitoring.AlertThresholds.PeerConnectionLimit` | `5` | Peer connection floor/limit check |

Example **lab** metadata fragment:

```python
# Family: A-toplevel monitoring | Status: candidate | Not a production control-plane default
metadata = {
    "role": "master",
    "config": {
        "Monitoring": {
            "Enabled": True,
            "MetricsInterval": "60s",
            "MaxMetricsHistory": 1440,
            "AlertThresholds": {
                "DiskSpace": 90,
                "MemoryUsage": 85,
                "CpuUsage": 90,
                "PinQueueLength": 100,
                "PeerConnectionLimit": 5,
            },
        }
    },
}
```

Auto-start behavior: if monitoring enabled and role is `master` or `worker`, constructor calls `start_monitoring()`.

---

## 6. Alerts and recovery actions (A-toplevel)

### 6.1 Threshold evaluation

`check_alert_thresholds` walks `metrics_data["nodes"]` and emits alert dicts with `level`, `type`, `node_id`, `value`, `threshold`, `timestamp`, `message`. Examples:

| Alert type | Trigger intent | Typical level |
|---|---|---|
| `cpu_usage_high` | CPU % above threshold | warning |
| `memory_usage_high` | Memory % above threshold | warning |
| `disk_usage_high` | Disk % above threshold | warning; critical if >95 |
| `pin_queue_long` | Pins queued above threshold | warning |
| Peer connection alerts | Peer counts vs limit | warning |

### 6.2 Recovery action types

`process_alerts` queues actions; `_execute_recovery_action` dispatches:

| Action type | Intent | Local node | Remote node | Status |
|---|---|---|---|---|
| `run_garbage_collection` | `ipfs repo gc` via kit | Implemented when `ipfs.ipfs_repo_gc` exists | **Not implemented** (logs warning) | experimental / partial |
| `reallocate_pins` | Move pins off unhealthy node | Depends on cluster APIs | Often stub/limited | experimental |
| `throttle_operations` | Reduce load | Heuristic | Limited | experimental |
| `reduce_memory_usage` | Drop caches / pressure relief | Heuristic | Limited | experimental |
| `connect_to_bootstrap_peers` | Heal peer isolation | Kit swarm connect hooks | Limited | experimental |
| `adjust_pin_concurrency` | Change pin worker pressure | Config tweak | Limited | experimental |
| `notify_admin` | Operator notification | Local log/notify path | Same | experimental |

**Safety rules:**

1. Automated actions are **not** an accepted multi-node control plane.
2. Remote actions frequently return “not implemented”—do not script production failovers on them.
3. GC and pin moves can delete or relocate content—require operator policy before enabling aggressive thresholds.
4. Prefer **notify-only** posture until Family authority and pinset ownership are explicit for the deployment.

---

## 7. Dashboard

`ClusterDashboard.generate_html_dashboard()` builds an HTML summary of status, metrics, and alerts for lab visualization. It may start a simple serve loop when configured; treat built-in UI as **basic**.

For sustained operational visibility, prefer exporting metrics to Prometheus/Grafana ([observability.md](observability.md)) while labeling series by node/role—not by inventing a control-plane default.

---

## 8. Lab usage patterns (scoped)

### 8.1 Top-level monitoring on an existing kit

```python
# Family: A-toplevel | Status: candidate/experimental
from ipfs_kit_py.cluster_monitoring import ClusterMonitoring, ClusterDashboard

# kit = already constructed ipfs_kit instance with metadata.role in {master, worker}
monitor = ClusterMonitoring(kit)
# If auto-start skipped (e.g. leecher), call:
# monitor.start_monitoring()

latest = monitor.get_latest_metrics()
alerts = monitor.check_alert_thresholds(latest) if latest else []

dashboard = ClusterDashboard(kit, monitoring_instance=monitor)
html = dashboard.generate_html_dashboard()

json_blob = monitor.export_metrics_json(time_range="24h", interval="1h")
```

### 8.2 Package MetricsCollector alone

```python
# Family: A-package | Status: candidate
# Do not pass role= — constructor does not accept it
from ipfs_kit_py.cluster.monitoring import MetricsCollector

collector = MetricsCollector(
    node_id="node-1",
    metrics_dir="~/.ipfs_kit/metrics",
    collection_interval=60,
    retention_days=7,
)
```

### 8.3 Kit enable flag

```python
# Family: A-package via ipfs_kit | Status: candidate (monitoring only)
# Does not establish production multi-node authority
from ipfs_kit_py.ipfs_kit import ipfs_kit

kit = ipfs_kit(
    metadata={
        "role": "worker",
        "enable_monitoring": True,
        # enable_cluster_management remains a separate, currently fragile path
    }
)
```

---

## 9. Health, partition, and degradation

| Scenario | Monitoring behavior | Operator action |
|---|---|---|
| High disk/memory/CPU on local node | Alerts; optional GC/throttle actions | Confirm content safety; prefer manual GC first |
| Peer count low | Peer connection alerts; bootstrap action | Check network and bootstrap list; Family B service health if used |
| Package heartbeat stub | Membership may not detect remote death | Do not trust auto-rebalance; use explicit B/C health if those planes run |
| Leader unhealthy (daemon-enhanced) | Election helpers re-elect by priority | Verify which Family A subset is actually running |
| MCP++ daemon health expiry | Family C health artifacts expire | Recover store; re-publish health CIDs |
| Multi-region helper degraded | `RegionStatus` degraded/unavailable | Routing helper only—not full partition solver |

Deeper partition notes: [CLUSTER_COORDINATION.md §7.2](../architecture/CLUSTER_COORDINATION.md).

---

## 10. Relationship to control-plane families

| If you operate… | Monitoring posture |
|---|---|
| Family A lab roles/tasks | Use A-toplevel or package collectors for **local** signals; do not claim HA |
| Family B pinset | Prefer upstream cluster metrics + kit wrapper status; pin queue thresholds may apply when data available |
| Family C claims | Use DurableCoordinationStore recovery/fencing tests and health artifacts—not ClusterDashboard as lease authority |
| Prometheus-only hosts | Fine for process SLOs; still not multi-node authority |

---

## 11. Scoped validation

| Concern | Tests / checks |
|---|---|
| Health monitor adjacency | `tests/unit/test_health_monitor_cluster.py` |
| Cluster backends / health | `tests/unit/test_cluster_backends.py` |
| Family B startup/API | `tests/unit/test_cluster_startup.py`, `test_cluster_api.py` |
| Family C durability | `tests/test_coordination_storage.py` |
| Package manager mismatch still present | `rg -n "role=self.initial_role" ipfs_kit_py/cluster/cluster_manager.py` |

### 11.1 Offline checks

```bash
test -s docs/operations/cluster_monitoring.md

# Both monitoring stacks still exist
rg -n "class (MetricsCollector|ClusterMonitor|ClusterMonitoring|ClusterDashboard)" \
  ipfs_kit_py/cluster/monitoring.py \
  ipfs_kit_py/cluster_monitoring.py

# MetricsCollector still has no role= parameter (mismatch sentinel)
rg -n "def __init__" -A8 ipfs_kit_py/cluster/monitoring.py | head -20

# Authority still Proposed
rg -q "Status: Proposed" docs/architecture/decisions/0008-cluster-control-plane-authority.md
```

---

## 12. What this runbook deliberately does not recommend

| Forbidden claim | Why |
|---|---|
| “Enable monitoring for production cluster HA” | Monitoring ≠ control-plane authority |
| “Automated reallocate_pins is safe multi-node failover” | Remote paths incomplete; authority unresolved |
| “Package ClusterManager + ClusterMonitor is the supported stack” | Manager construction broken at call sites |
| “Dashboard replaces Prometheus” | Built-in HTML is basic; different purpose |
| “Alert recovery defines the production pinset owner” | Pinset ownership is Family B or unselected |

---

## 13. Related documents

| Document | Relationship |
|---|---|
| [cluster_management.md](cluster_management.md) | Families, enablement, dual managers |
| [cluster_state.md](cluster_state.md) | State planes feeding status |
| [CLUSTER_COORDINATION.md](../architecture/CLUSTER_COORDINATION.md) | Health/partition architecture |
| [ADR-0008](../architecture/decisions/0008-cluster-control-plane-authority.md) | Proposed control-plane authority |
| [observability.md](observability.md) | Prometheus/Grafana process metrics |
| [performance_metrics.md](performance_metrics.md) | Performance metric narrative |
| [coordination-storage.md](../coordination-storage.md) | Family C health artifacts |

---

## 14. Change triggers

Re-verify when:

- Package monitoring constructors or kit `_setup_monitoring` change
- Top-level alert thresholds or recovery action implementations land remote paths
- ADR-0008 acceptance changes allowed “production” wording
- Prometheus metric names/labels change
- Package `ClusterManager` composition is repaired (monitor wiring becomes testable end-to-end)

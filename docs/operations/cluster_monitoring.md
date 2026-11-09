# Cluster Monitoring & Dashboard

`ipfs-kit-py` includes features for monitoring the health and performance of the cluster nodes and generating dashboards for visualization. The core logic resides in `cluster_monitoring.py`, primarily within the `ClusterMonitoring` and `ClusterDashboard` classes.

## Overview

Monitoring provides insights into the operational status of the cluster, helps identify potential issues early, and can automate recovery actions.

**Key Concepts:**

*   **Metrics Collection**: Periodically gathers metrics from local and potentially remote cluster nodes. Metrics can include:
    *   System resources (CPU, memory, disk, network usage).
    *   IPFS-specific stats (repo size, pin count, peer count, bandwidth usage).
    *   Cluster state info (number of nodes by role/status, task queue length, task success/failure rates).
    *   Cache performance (hit rates, sizes).
*   **Alerting**: Defines thresholds for various metrics. When a threshold is breached, an alert is generated.
*   **Recovery Actions**: Predefined actions that can be automatically triggered in response to specific alerts (e.g., run IPFS GC on high disk usage, reallocate pins from a failing node, notify an administrator).
*   **Metrics Aggregation**: Can aggregate collected metrics over time ranges (e.g., hourly averages, daily totals).
*   **Exporting**: Allows exporting aggregated metrics in formats like JSON or CSV.
*   **Dashboard Generation**: Creates a (likely HTML) dashboard summarizing the current cluster status, key metrics, and active alerts.

## Implementation (`ClusterMonitoring` & `ClusterDashboard`)

*   **`ClusterMonitoring`**:
    *   Runs a background thread (`_metrics_collection_thread`) to periodically collect metrics.
    *   Stores collected metrics (potentially in memory or a time-series database).
    *   Evaluates defined alert rules (`check_alert_thresholds`).
    *   Processes alerts and triggers corresponding recovery actions (`process_alerts`, `_execute_recovery_action`).
    *   Provides methods to get current/aggregated metrics (`get_latest_metrics`, `aggregate_metrics`) and export them (`export_metrics_json`, `export_metrics_csv`).
*   **`ClusterDashboard`**:
    *   Likely uses data provided by `ClusterMonitoring`.
    *   Generates an HTML representation of the cluster status (`generate_html_dashboard`).
    *   May run its own simple web server or integrate with the main API server to serve the dashboard.

## Configuration

Monitoring and dashboard features are configured under `cluster.monitoring` and `cluster.dashboard`:

```python
# Example configuration snippet
config = {
    'cluster': {
        'monitoring': {
            'enabled': True,
            'collection_interval_seconds': 60,
            'metrics_history_duration_hours': 24,
            'alerts': [
                {'metric': 'node.disk_usage_percent', 'threshold': 90, 'operator': '>=', 'severity': 'warning', 'action': 'run_gc'},
                {'metric': 'node.memory_usage_percent', 'threshold': 95, 'operator': '>=', 'severity': 'critical', 'action': 'notify_admin'},
                {'metric': 'node.status', 'threshold': 'Offline', 'operator': '==', 'severity': 'critical', 'duration_minutes': 5, 'action': 'reallocate_pins'},
                # Add more alerts based on available metrics
            ],
            'recovery_actions': { # Define how actions are executed
                'run_gc': {'command': 'ipfs repo gc', 'target': 'alerting_node'},
                'reallocate_pins': {'method': 'cluster_manager.reallocate_pins', 'target': 'alerting_node'},
                'notify_admin': {'script': '/path/to/notify_script.sh', 'args': ['{node_id}', '{details}']}
            }
        },
        'dashboard': {
            'enabled': True,
            'refresh_interval_seconds': 30,
            # Potentially host/port if running standalone server
            # 'host': '0.0.0.0',
            # 'port': 9091
        }
        # ... other cluster config
    }
    # ... other ipfs-kit-py config
}
```

## Usage

*   **Automatic Operation**: When enabled, monitoring runs in the background. Alerts and recovery actions are processed automatically.
*   **Accessing Metrics**: Use methods like `get_latest_metrics` or `aggregate_metrics` on the `ClusterMonitoring` instance (if accessible) or potentially via dedicated API endpoints.
*   **Viewing Dashboard**: Access the dashboard URL if served via the API or a standalone server.
*   **Exporting Data**: Use `export_metrics_json` or `export_metrics_csv` for offline analysis.

## Benefits

*   **Proactive Issue Detection**: Identify problems like resource exhaustion or node failures before they cause major outages.
*   **Automated Recovery**: Reduce manual intervention for common issues.
*   **Performance Insights**: Understand cluster load and resource utilization patterns.
*   **Centralized Overview**: The dashboard provides a quick status check.

## Considerations

*   **Metrics Overhead**: Collecting metrics consumes some resources (CPU, network). Collection intervals should be balanced.
*   **Alert Tuning**: Setting appropriate alert thresholds requires understanding normal operating ranges to avoid false positives or negatives.
*   **Recovery Action Safety**: Automated actions should be carefully designed and tested to avoid unintended consequences.
*   **Dashboard Scope**: The built-in dashboard might be basic; for advanced visualization, exporting metrics to dedicated systems like Prometheus/Grafana (see `prometheus_exporter.py`) might be preferred.

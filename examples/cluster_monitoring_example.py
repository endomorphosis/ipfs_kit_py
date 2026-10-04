import logging
import time
import os
import random
import json
# Assuming access to internal components for demonstration
try:
    from ipfs_kit_py.cluster_monitoring import ClusterMonitoring
    # Need a mock kit instance to pass
    class MockIPFSKit:
        def __init__(self, config):
            self.config = config
            self.peer_id = config.get('cluster', {}).get('node_id', 'monitor_node')
            # Mock methods needed by ClusterMonitoring
            self.cluster_manager = self # Simulate having cluster manager methods if needed
            self.monitoring = None # Will be set later

        def get_config_value(self, keys, default=None):
            val = self.config
            try:
                for key in keys:
                    val = val[key]
                return val
            except (KeyError, TypeError):
                return default

        # Mock methods potentially called by recovery actions
        def ipfs_repo_gc(self, node_id=None):
             log.info(f"MOCK: Running GC on node {node_id or self.peer_id}")
             return {"success": True}

        def reallocate_pins(self, node_id):
             log.info(f"MOCK: Reallocating pins from node {node_id}")
             return {"success": True}

        def execute_external_script(self, script_path, args):
             log.info(f"MOCK: Executing script {script_path} with args {args}")
             return {"success": True, "output": "Script executed (simulated)"}

except ImportError:
    logging.error("Required classes not found. Ensure cluster features are installed/available.")
    class ClusterMonitoring: pass
    class MockIPFSKit: pass

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger("MonitoringExample")

# --- Configuration ---
# Example config enabling monitoring with alerts and actions
# Create a dummy script path for the notification action
dummy_script_path = os.path.abspath("./dummy_notify_script.sh")
with open(dummy_script_path, "w") as f:
    f.write("#!/bin/bash\necho 'Notification script called with args: $@'\n")
os.chmod(dummy_script_path, 0o755)


config = {
    'cluster': {
        'node_id': 'monitor_node_1',
        'monitoring': {
            'enabled': True, # Usually controls background thread, we'll call manually
            'collection_interval_seconds': 60, # Ignored in manual example
            'metrics_history_duration_hours': 1, # Keep 1 hour of history
            'alerts': [
                {'metric': 'node.disk_usage_percent', 'threshold': 85, 'operator': '>=', 'severity': 'warning', 'action': 'run_gc', 'duration_minutes': 1},
                {'metric': 'node.memory_usage_percent', 'threshold': 90, 'operator': '>=', 'severity': 'critical', 'action': 'notify_admin', 'duration_minutes': 5},
                {'metric': 'node.status', 'threshold': 'Offline', 'operator': '==', 'severity': 'critical', 'action': 'reallocate_pins', 'duration_minutes': 2},
            ],
            'recovery_actions': {
                'run_gc': {'method': 'ipfs_repo_gc', 'target': 'alerting_node'},
                'reallocate_pins': {'method': 'reallocate_pins', 'target': 'alerting_node'},
                'notify_admin': {'script': dummy_script_path, 'args': ['{severity}', '{node_id}', '{metric}={value}']}
            }
        }
        # Add other cluster config if needed
    }
}

# --- Main Example Logic ---
def main():
    log.info("Demonstrating Cluster Monitoring concepts.")

    mock_kit = MockIPFSKit(config)

    try:
        # Initialize ClusterMonitoring
        # Pass the mock kit instance which holds config and mock methods
        monitoring = ClusterMonitoring(ipfs_kit_instance=mock_kit)
        mock_kit.monitoring = monitoring # Allow access if needed
        log.info("ClusterMonitoring initialized.")

        # --- Simulate Metrics Collection ---
        # In a real scenario, collect_cluster_metrics runs periodically.
        # Here, we simulate adding some metrics data manually.
        log.info("\n--- Simulating Metrics Collection ---")
        metrics_data_normal = {
            'timestamp': time.time(),
            'nodes': {
                'monitor_node_1': {'disk_usage_percent': 50, 'memory_usage_percent': 60, 'status': 'Online', 'cpu_load': 0.5},
                'worker_node_2': {'disk_usage_percent': 70, 'memory_usage_percent': 75, 'status': 'Online', 'cpu_load': 0.8},
            },
            'cluster': {'task_queue_length': 5}
        }
        # Manually add to internal storage (or use a dedicated method if available)
        monitoring._metrics_history.append(metrics_data_normal)
        log.info(f"Added normal metrics data: {json.dumps(metrics_data_normal, indent=2)}")

        time.sleep(1) # Ensure timestamp difference

        metrics_data_alerting = {
            'timestamp': time.time(),
            'nodes': {
                'monitor_node_1': {'disk_usage_percent': 60, 'memory_usage_percent': 92, 'status': 'Online', 'cpu_load': 0.6}, # High memory
                'worker_node_2': {'disk_usage_percent': 88, 'memory_usage_percent': 80, 'status': 'Online', 'cpu_load': 0.9}, # High disk
                'worker_node_3': {'disk_usage_percent': 40, 'memory_usage_percent': 50, 'status': 'Offline', 'cpu_load': 0.0}, # Offline
            },
            'cluster': {'task_queue_length': 15}
        }
        monitoring._metrics_history.append(metrics_data_alerting)
        log.info(f"Added alerting metrics data: {json.dumps(metrics_data_alerting, indent=2)}")


        # --- Check Alerts ---
        log.info("\n--- Checking Alert Thresholds ---")
        # Normally happens within the monitoring loop, call manually here
        latest_metrics = monitoring.get_latest_metrics()
        if latest_metrics:
            alerts = monitoring.check_alert_thresholds(latest_metrics)
            log.info(f"Generated Alerts ({len(alerts)}):")
            for alert in alerts:
                 log.info(f"  - Node: {alert['node_id']}, Metric: {alert['metric']}, Value: {alert['value']}, Severity: {alert['severity']}, Action: {alert['action']}")
        else:
            log.warning("No metrics data available to check alerts.")

        # --- Process Alerts & Trigger Actions (Conceptual) ---
        log.info("\n--- Processing Alerts (Conceptual) ---")
        # This normally runs in the background loop, processing active alerts
        # and triggering actions based on duration and configuration.
        # We simulate the potential outcome based on the alerts found above.
        active_alerts = monitoring.process_alerts(alerts) # Simulate processing
        log.info(f"Processing resulted in {len(active_alerts)} active alerts requiring action (potentially after duration).")
        # In a real run, _execute_pending_actions would be called by the loop.
        # Example manual trigger simulation (doesn't respect duration logic):
        for alert in active_alerts:
             log.info(f"  -> Simulating execution for alert on {alert['node_id']} (Action: {alert['action']})")
             # monitoring._execute_recovery_action(alert) # This would call the actual mock methods

        # --- Retrieve Metrics ---
        log.info("\n--- Retrieving Metrics ---")
        latest = monitoring.get_latest_metrics()
        log.info(f"Latest Metrics: {json.dumps(latest, indent=2)}")

        # Aggregate metrics (example: last 10 minutes, 1 min interval)
        # Note: Requires more historical data for meaningful aggregation
        aggregated = monitoring.aggregate_metrics(time_range="10m", interval="1m")
        log.info(f"\nAggregated Metrics (last 10m): {json.dumps(aggregated, indent=2)}")

        # --- Export Metrics ---
        log.info("\n--- Exporting Metrics ---")
        try:
            json_export = monitoring.export_metrics_json(time_range="1h")
            with open("./monitoring_export.json", "w") as f:
                f.write(json_export)
            log.info("Exported metrics to monitoring_export.json")

            csv_export = monitoring.export_metrics_csv(time_range="1h")
            with open("./monitoring_export.csv", "w") as f:
                f.write(csv_export)
            log.info("Exported metrics to monitoring_export.csv")
        except Exception as e:
            log.error(f"Failed to export metrics: {e}")


    except Exception as e:
        log.error(f"An error occurred during the monitoring example: {e}", exc_info=True)

    finally:
        log.info("\nCluster monitoring example finished.")
        # Clean up dummy script
        if os.path.exists(dummy_script_path):
            os.remove(dummy_script_path)

if __name__ == "__main__":
    main()

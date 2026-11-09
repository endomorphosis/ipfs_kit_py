"""
Migration Monitoring Integration

This module integrates the MCP Migration Controller with the monitoring system,
providing real-time metrics and alerts for migration operations.
"""

import logging
import time
import json
import threading
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

# Configure logger
logger = logging.getLogger(__name__)


class MigrationMonitor:
    """
    Provides monitoring capabilities for the Migration Controller.
    
    This class integrates with the MCP monitoring system to provide real-time
    metrics and insights about migration operations, including:
    - Migration success/failure rates
    - Performance metrics (transfer speeds, latency)
    - Backend health monitoring
    - Cost optimization metrics
    - Alerting for migration issues
    """
    
    def __init__(self, migration_controller, monitoring_system=None):
        """
        Initialize the migration monitor.
        
        Args:
            migration_controller: The migration controller instance to monitor
            monitoring_system: Optional monitoring system to integrate with
        """
        self.migration_controller = migration_controller
        self.monitoring_system = monitoring_system
        self.active = False
        self.update_interval = 60  # seconds
        self.update_thread = None
        self.stop_event = threading.Event()
        
        # Metrics storage
        self.metrics = {
            "overall": {
                "total_migrations": 0,
                "successful_migrations": 0,
                "failed_migrations": 0,
                "bytes_transferred": 0,
                "average_transfer_speed": 0  # bytes per second
            },
            "backends": {},
            "time_series": {
                "migration_counts": [],  # List of (timestamp, count) tuples
                "transfer_rates": []     # List of (timestamp, bytes_per_second) tuples
            },
            "alerts": []
        }
        
        # Thresholds for alerts
        self.alert_thresholds = {
            "failure_rate": 0.2,          # Alert if failure rate exceeds 20%
            "slow_transfer": 50 * 1024,   # Alert if transfer speed below 50 KB/s
            "backend_error_rate": 0.1     # Alert if backend error rate exceeds 10%
        }

    def start(self):
        """Start the monitoring system."""
        if self.active:
            logger.warning("Migration monitor already active")
            return
            
        self.active = True
        self.stop_event.clear()
        
        # Initialize metrics from current state
        self._update_metrics()
        
        # Start monitoring thread
        self.update_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True
        )
        self.update_thread.start()
        
        logger.info("Started migration monitoring")
        
        # Register with monitoring system if available
        if self.monitoring_system:
            try:
                self.monitoring_system.register_component(
                    "migration_controller",
                    self.get_metrics,
                    self.get_health_status
                )
                logger.info("Registered with monitoring system")
            except Exception as e:
                logger.error(f"Failed to register with monitoring system: {e}")

    def stop(self):
        """Stop the monitoring system."""
        if not self.active:
            return
            
        self.active = False
        self.stop_event.set()
        
        if self.update_thread:
            self.update_thread.join(timeout=5)
            
        logger.info("Stopped migration monitoring")
        
        # Unregister from monitoring system if available
        if self.monitoring_system:
            try:
                self.monitoring_system.unregister_component("migration_controller")
                logger.info("Unregistered from monitoring system")
            except Exception as e:
                logger.error(f"Failed to unregister from monitoring system: {e}")

    def _monitoring_loop(self):
        """Main monitoring loop that periodically updates metrics."""
        logger.info("Migration monitoring loop started")
        
        while not self.stop_event.is_set():
            try:
                # Update metrics
                self._update_metrics()
                
                # Check for alert conditions
                self._check_alerts()
                
                # Sleep until next update
                self.stop_event.wait(self.update_interval)
                
            except Exception as e:
                logger.exception(f"Error in migration monitoring loop: {e}")
                # Don't exit the loop on error, just wait for next cycle
                self.stop_event.wait(self.update_interval)
                
        logger.info("Migration monitoring loop stopped")

    def _update_metrics(self):
        """Update metrics from the migration controller."""
        try:
            # Get current statistics
            stats = self.migration_controller.get_statistics()
            
            # Update overall metrics
            self.metrics["overall"]["total_migrations"] = stats["total_migrations"]
            self.metrics["overall"]["successful_migrations"] = stats["successful_migrations"]
            self.metrics["overall"]["failed_migrations"] = stats["failed_migrations"]
            self.metrics["overall"]["bytes_transferred"] = stats["bytes_transferred"]
            
            # Calculate success rate
            if stats["total_migrations"] > 0:
                success_rate = stats["successful_migrations"] / stats["total_migrations"]
                self.metrics["overall"]["success_rate"] = success_rate
            else:
                self.metrics["overall"]["success_rate"] = 1.0  # No migrations = 100% success
                
            # Update backend-specific metrics
            for backend, backend_stats in stats.get("backend_stats", {}).items():
                if backend not in self.metrics["backends"]:
                    self.metrics["backends"][backend] = {
                        "outgoing_migrations": 0,
                        "outgoing_bytes": 0,
                        "incoming_migrations": 0,
                        "incoming_bytes": 0,
                        "error_count": 0,
                        "last_error": None
                    }
                
                # Update existing metrics
                self.metrics["backends"][backend].update({
                    "outgoing_migrations": backend_stats.get("outgoing_migrations", 0),
                    "outgoing_bytes": backend_stats.get("outgoing_bytes", 0),
                    "incoming_migrations": backend_stats.get("incoming_migrations", 0),
                    "incoming_bytes": backend_stats.get("incoming_bytes", 0)
                })
            
            # Update time series data
            timestamp = int(time.time())
            
            # Calculate transfer rate for the last interval
            current_bytes = stats["bytes_transferred"]
            current_time = timestamp
            
            if len(self.metrics["time_series"]["transfer_rates"]) > 0:
                last_timestamp, last_bytes = self.metrics["time_series"]["transfer_rates"][-1]
                time_diff = current_time - last_timestamp
                
                if time_diff > 0:
                    bytes_diff = current_bytes - last_bytes
                    transfer_rate = bytes_diff / time_diff
                    
                    # Only record if there's been a change
                    if bytes_diff > 0:
                        self.metrics["time_series"]["transfer_rates"].append((current_time, transfer_rate))
                        
                        # Update average transfer speed
                        if len(self.metrics["time_series"]["transfer_rates"]) > 1:
                            rates = [rate for _, rate in self.metrics["time_series"]["transfer_rates"]]
                            self.metrics["overall"]["average_transfer_speed"] = sum(rates) / len(rates)
            else:
                # First data point
                self.metrics["time_series"]["transfer_rates"].append((current_time, 0))
            
            # Add migration count
            self.metrics["time_series"]["migration_counts"].append((current_time, stats["total_migrations"]))
            
            # Trim time series data to keep only last 24 hours
            cutoff_time = current_time - (24 * 60 * 60)
            self.metrics["time_series"]["transfer_rates"] = [
                (ts, rate) for ts, rate in self.metrics["time_series"]["transfer_rates"]
                if ts >= cutoff_time
            ]
            self.metrics["time_series"]["migration_counts"] = [
                (ts, count) for ts, count in self.metrics["time_series"]["migration_counts"]
                if ts >= cutoff_time
            ]
            
            logger.debug("Updated migration metrics")
            
        except Exception as e:
            logger.error(f"Error updating migration metrics: {e}")

    def _check_alerts(self):
        """Check for conditions that should trigger alerts."""
        try:
            # Check overall failure rate
            if self.metrics["overall"]["total_migrations"] > 10:  # Only alert after sufficient data
                failure_rate = self.metrics["overall"]["failed_migrations"] / self.metrics["overall"]["total_migrations"]
                
                if failure_rate >= self.alert_thresholds["failure_rate"]:
                    self._add_alert(
                        "High Migration Failure Rate",
                        f"Failure rate is {failure_rate:.1%}, threshold is {self.alert_thresholds['failure_rate']:.1%}",
                        "high"
                    )
            
            # Check transfer speed
            avg_speed = self.metrics["overall"]["average_transfer_speed"]
            if avg_speed > 0 and avg_speed < self.alert_thresholds["slow_transfer"]:
                self._add_alert(
                    "Slow Migration Transfer Rate",
                    f"Average transfer speed is {avg_speed/1024:.2f} KB/s, threshold is {self.alert_thresholds['slow_transfer']/1024:.2f} KB/s",
                    "medium"
                )
                
            # Check backend-specific metrics
            for backend, stats in self.metrics["backends"].items():
                total_migrations = stats["outgoing_migrations"] + stats["incoming_migrations"]
                error_count = stats.get("error_count", 0)
                
                if total_migrations > 5 and error_count > 0:  # Only check after sufficient data
                    error_rate = error_count / total_migrations
                    
                    if error_rate >= self.alert_thresholds["backend_error_rate"]:
                        self._add_alert(
                            f"High Error Rate for {backend} Backend",
                            f"Error rate is {error_rate:.1%}, threshold is {self.alert_thresholds['backend_error_rate']:.1%}",
                            "high"
                        )
            
        except Exception as e:
            logger.error(f"Error checking migration alerts: {e}")

    def _add_alert(self, title, message, severity="medium"):
        """
        Add a new alert to the alerts list.
        
        Args:
            title: Alert title
            message: Alert message
            severity: Alert severity (low, medium, high)
        """
        alert = {
            "id": str(len(self.metrics["alerts"]) + 1),
            "title": title,
            "message": message,
            "severity": severity,
            "timestamp": int(time.time()),
            "acknowledged": False
        }
        
        # Add to alerts list
        self.metrics["alerts"].append(alert)
        
        # Log the alert
        log_level = {
            "low": logging.INFO,
            "medium": logging.WARNING,
            "high": logging.ERROR
        }.get(severity, logging.WARNING)
        
        logger.log(log_level, f"Migration Alert: {title} - {message}")
        
        # Send to monitoring system if available
        if self.monitoring_system:
            try:
                self.monitoring_system.report_alert("migration_controller", alert)
            except Exception as e:
                logger.error(f"Failed to report alert to monitoring system: {e}")

    def acknowledge_alert(self, alert_id):
        """
        Acknowledge an alert.
        
        Args:
            alert_id: ID of the alert to acknowledge
            
        Returns:
            True if acknowledged, False if not found
        """
        for alert in self.metrics["alerts"]:
            if alert["id"] == alert_id:
                alert["acknowledged"] = True
                logger.info(f"Alert {alert_id} acknowledged: {alert['title']}")
                return True
                
        return False

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current migration metrics.
        
        Returns:
            Dictionary with metrics
        """
        return self.metrics

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status of the migration system.
        
        Returns:
            Dictionary with health status information
        """
        # Determine overall health
        health_status = "healthy"
        details = {}
        
        # Check for unacknowledged high severity alerts
        high_alerts = [
            alert for alert in self.metrics["alerts"]
            if alert["severity"] == "high" and not alert["acknowledged"]
        ]
        
        if high_alerts:
            health_status = "unhealthy"
            details["high_alerts"] = len(high_alerts)
        
        # Check migration success rate
        success_rate = self.metrics["overall"].get("success_rate", 1.0)
        if success_rate < 0.8:  # Less than 80% success
            health_status = "degraded" if health_status == "healthy" else health_status
            details["success_rate"] = f"{success_rate:.1%}"
        
        # Check backend health
        unhealthy_backends = []
        for backend, stats in self.metrics["backends"].items():
            if stats.get("error_count", 0) > 5:  # More than 5 errors
                unhealthy_backends.append(backend)
                
        if unhealthy_backends:
            health_status = "degraded" if health_status == "healthy" else health_status
            details["unhealthy_backends"] = unhealthy_backends
        
        return {
            "status": health_status,
            "timestamp": int(time.time()),
            "details": details
        }

    def get_alerts(self, include_acknowledged=False) -> List[Dict[str, Any]]:
        """
        Get current alerts.
        
        Args:
            include_acknowledged: Whether to include acknowledged alerts
            
        Returns:
            List of alert dictionaries
        """
        if include_acknowledged:
            return self.metrics["alerts"]
        else:
            return [alert for alert in self.metrics["alerts"] if not alert["acknowledged"]]

    def get_backend_health(self, backend_name=None) -> Dict[str, Any]:
        """
        Get health information for backends.
        
        Args:
            backend_name: Optional backend name to get specific info
            
        Returns:
            Dictionary with backend health information
        """
        if backend_name:
            # Return specific backend
            if backend_name in self.metrics["backends"]:
                stats = self.metrics["backends"][backend_name]
                total_migrations = stats["outgoing_migrations"] + stats["incoming_migrations"]
                error_rate = stats.get("error_count", 0) / total_migrations if total_migrations > 0 else 0
                
                health_status = "healthy"
                if error_rate > self.alert_thresholds["backend_error_rate"]:
                    health_status = "unhealthy"
                elif error_rate > 0:
                    health_status = "degraded"
                
                return {
                    "backend": backend_name,
                    "status": health_status,
                    "error_rate": error_rate,
                    "total_migrations": total_migrations,
                    "outgoing_migrations": stats["outgoing_migrations"],
                    "incoming_migrations": stats["incoming_migrations"],
                    "last_error": stats.get("last_error")
                }
            else:
                return {"error": f"Backend {backend_name} not found"}
        else:
            # Return all backends
            results = {}
            for backend, stats in self.metrics["backends"].items():
                total_migrations = stats["outgoing_migrations"] + stats["incoming_migrations"]
                error_rate = stats.get("error_count", 0) / total_migrations if total_migrations > 0 else 0
                
                health_status = "healthy"
                if error_rate > self.alert_thresholds["backend_error_rate"]:
                    health_status = "unhealthy"
                elif error_rate > 0:
                    health_status = "degraded"
                
                results[backend] = {
                    "status": health_status,
                    "error_rate": error_rate,
                    "total_migrations": total_migrations
                }
            
            return results

    def set_alert_thresholds(self, thresholds: Dict[str, Any]):
        """
        Update alert thresholds.
        
        Args:
            thresholds: Dictionary with threshold values to update
        """
        for key, value in thresholds.items():
            if key in self.alert_thresholds:
                self.alert_thresholds[key] = value
                
        logger.info(f"Updated alert thresholds: {self.alert_thresholds}")

    def generate_report(self, format="json", since=None) -> str:
        """
        Generate a report of migration activities.
        
        Args:
            format: Output format (json, text, html)
            since: Optional timestamp to filter data (seconds since epoch)
            
        Returns:
            Report string in the specified format
        """
        # Filter metrics by time if needed
        filtered_metrics = self.metrics.copy()
        
        if since is not None:
            # Filter time series data
            filtered_metrics["time_series"] = {
                "migration_counts": [
                    (ts, count) for ts, count in self.metrics["time_series"]["migration_counts"]
                    if ts >= since
                ],
                "transfer_rates": [
                    (ts, rate) for ts, rate in self.metrics["time_series"]["transfer_rates"]
                    if ts >= since
                ]
            }
            
            # Filter alerts
            filtered_metrics["alerts"] = [
                alert for alert in self.metrics["alerts"]
                if alert["timestamp"] >= since
            ]
        
        # Generate report in specified format
        if format == "json":
            return json.dumps(filtered_metrics, indent=2)
        elif format == "html":
            # Simple HTML report
            html = "<html><head><title>Migration Report</title></head><body>"
            html += f"<h1>Migration Report</h1>"
            html += f"<p>Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>"
            
            html += "<h2>Overall Statistics</h2>"
            html += "<table border='1'><tr><th>Metric</th><th>Value</th></tr>"
            for key, value in filtered_metrics["overall"].items():
                if key == "average_transfer_speed":
                    html += f"<tr><td>{key}</td><td>{value/1024:.2f} KB/s</td></tr>"
                elif key == "bytes_transferred":
                    html += f"<tr><td>{key}</td><td>{value/1024/1024:.2f} MB</td></tr>"
                elif key == "success_rate":
                    html += f"<tr><td>{key}</td><td>{value:.1%}</td></tr>"
                else:
                    html += f"<tr><td>{key}</td><td>{value}</td></tr>"
            html += "</table>"
            
            # Add more sections for backends, alerts, etc.
            html += "</body></html>"
            return html
        else:
            # Text format
            text = "MIGRATION REPORT\n"
            text += "===============\n\n"
            text += f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            text += "OVERALL STATISTICS\n"
            text += "-----------------\n"
            for key, value in filtered_metrics["overall"].items():
                if key == "average_transfer_speed":
                    text += f"{key}: {value/1024:.2f} KB/s\n"
                elif key == "bytes_transferred":
                    text += f"{key}: {value/1024/1024:.2f} MB\n"
                elif key == "success_rate":
                    text += f"{key}: {value:.1%}\n"
                else:
                    text += f"{key}: {value}\n"
            
            text += "\nBACKEND STATISTICS\n"
            text += "------------------\n"
            for backend, stats in filtered_metrics["backends"].items():
                text += f"{backend}:\n"
                for key, value in stats.items():
                    if "bytes" in key:
                        text += f"  {key}: {value/1024/1024:.2f} MB\n"
                    else:
                        text += f"  {key}: {value}\n"
                text += "\n"
            
            # Add sections for alerts
            text += "ALERTS\n"
            text += "------\n"
            if filtered_metrics["alerts"]:
                for alert in filtered_metrics["alerts"]:
                    text += f"[{alert['severity'].upper()}] {alert['title']}\n"
                    text += f"  {alert['message']}\n"
                    text += f"  Time: {datetime.fromtimestamp(alert['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}\n"
                    text += f"  Acknowledged: {alert['acknowledged']}\n\n"
            else:
                text += "No alerts in the selected time period.\n"
            
            return text
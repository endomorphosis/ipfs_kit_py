"""
Monitoring API Routes for MCP Server

This module provides FastAPI routes for the enhanced monitoring system
as specified in the MCP roadmap for Phase 1: Core Functionality Enhancements (Q3 2025).

Features:
- Metrics endpoints (JSON and Prometheus formats)
- Health check API
- Alerting system API
- Monitoring dashboards integration
"""

import os
import time
import json
import logging
from typing import Dict, Any, List, Optional, Union
from fastapi import APIRouter, Request, Response, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse, PlainTextResponse, HTMLResponse

from ..monitoring import MonitoringManager
from ..monitoring.prometheus import PrometheusIntegration, PrometheusConfig
from ..monitoring.health import HealthCheckManager, HealthStatus
from ..monitoring.alerts.manager import AlertManager, AlertRule, Alert, AlertSeverity, AlertState

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v0/monitoring", tags=["monitoring"])


class MonitoringAPIService:
    """Service class providing monitoring API endpoints."""
    
    def __init__(
        self,
        monitoring_manager: MonitoringManager,
        prometheus_integration: PrometheusIntegration,
        health_manager: HealthCheckManager,
        alert_manager: Optional[AlertManager] = None,
    ):
        """
        Initialize the monitoring API service.
        
        Args:
            monitoring_manager: MCP monitoring manager
            prometheus_integration: Prometheus integration
            health_manager: Health check manager
            alert_manager: Optional alert manager
        """
        self.monitoring = monitoring_manager
        self.prometheus = prometheus_integration
        self.health = health_manager
        self.alerts = alert_manager
        
        # Register routes with the router
        self._register_routes()
    
    def _register_routes(self) -> None:
        """Register API routes with the router."""
        # Metrics routes
        @router.get(
            "/metrics",
            summary="Get all metrics",
            description="Get all collected metrics in JSON format",
            response_description="JSON object with all metrics",
        )
        async def get_metrics(
            request: Request,
            format: str = Query("json", description="Output format (json or prometheus)"),
        ) -> Union[Dict[str, Any], str]:
            """Get all metrics in JSON or Prometheus format."""
            # Update collection time
            self.prometheus.last_scrape_time = time.time()
            
            # Collect custom metrics before returning
            self.prometheus.collect_custom_metrics()
            
            # Return in requested format
            if format.lower() == "prometheus":
                return PlainTextResponse(self.monitoring.get_metrics(format="prometheus"))
            else:
                return self.monitoring.get_metrics()
        
        @router.get(
            "/metrics/{tag}",
            summary="Get metrics by tag",
            description="Get metrics filtered by tag",
            response_description="JSON object with filtered metrics",
        )
        async def get_metrics_by_tag(
            request: Request,
            tag: str,
        ) -> Dict[str, Any]:
            """Get metrics filtered by tag."""
            # Map tag string to MetricTag enum
            try:
                metric_tag = self.monitoring.metrics.MetricTag(tag.upper())
                return self.monitoring.metrics.get_metrics(tag=metric_tag)
            except ValueError:
                # Invalid tag
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid metric tag: {tag}"
                )
        
        # Health check routes
        @router.get(
            "/health",
            summary="Get system health",
            description="Get overall system health status and summary",
            response_description="Health status summary",
        )
        async def get_health() -> Dict[str, Any]:
            """Get overall system health status."""
            summary = self.health.get_health_summary()
            
            # Add response status code based on health
            status_code = status.HTTP_200_OK
            if summary["status"] == HealthStatus.DEGRADED:
                status_code = status.HTTP_207_MULTI_STATUS
            elif summary["status"] == HealthStatus.UNHEALTHY:
                status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            elif summary["status"] == HealthStatus.UNKNOWN:
                status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            
            return JSONResponse(
                content=summary,
                status_code=status_code
            )
        
        @router.get(
            "/health/checks",
            summary="Get all health checks",
            description="Get information about all configured health checks",
            response_description="List of health checks",
        )
        async def get_health_checks() -> Dict[str, Any]:
            """Get all health checks."""
            checks = self.health.get_checks()
            
            # Convert to dictionary
            check_data = {}
            for check in checks:
                check_data[check.id] = {
                    "id": check.id,
                    "name": check.name,
                    "description": check.description,
                    "check_type": check.check_type,
                    "target": check.target,
                    "interval": check.interval,
                    "timeout": check.timeout,
                    "critical": check.critical,
                    "enabled": check.enabled,
                    "labels": check.labels,
                }
            
            return {
                "checks": check_data,
                "count": len(checks)
            }
        
        @router.get(
            "/health/checks/{check_id}",
            summary="Get health check by ID",
            description="Get information about a specific health check",
            response_description="Health check details",
        )
        async def get_health_check(check_id: str) -> Dict[str, Any]:
            """Get a specific health check."""
            check = self.health.get_check(check_id)
            if not check:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Health check not found: {check_id}"
                )
            
            # Get latest result
            result = self.health.get_result(check_id)
            
            # Get history
            history = self.health.get_result_history(check_id, limit=10)
            
            # Convert to dictionary
            check_data = {
                "id": check.id,
                "name": check.name,
                "description": check.description,
                "check_type": check.check_type,
                "target": check.target,
                "interval": check.interval,
                "timeout": check.timeout,
                "critical": check.critical,
                "enabled": check.enabled,
                "labels": check.labels,
            }
            
            # Add result if available
            if result:
                check_data["latest_result"] = {
                    "status": result.status,
                    "timestamp": result.timestamp.isoformat(),
                    "duration_ms": result.duration_ms,
                    "details": result.details,
                    "error": result.error,
                }
            
            # Add history if available
            if history:
                check_data["history"] = [
                    {
                        "status": r.status,
                        "timestamp": r.timestamp.isoformat(),
                        "duration_ms": r.duration_ms,
                        "error": r.error,
                    }
                    for r in history
                ]
            
            return check_data
        
        @router.post(
            "/health/checks/{check_id}/run",
            summary="Run health check",
            description="Manually run a specific health check",
            response_description="Health check result",
        )
        async def run_health_check(check_id: str) -> Dict[str, Any]:
            """Run a specific health check."""
            # Check if health check exists
            check = self.health.get_check(check_id)
            if not check:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Health check not found: {check_id}"
                )
            
            # Run check
            result = self.health.run_check(check_id)
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to run health check: {check_id}"
                )
            
            # Return result
            return {
                "id": check_id,
                "status": result.status,
                "timestamp": result.timestamp.isoformat(),
                "duration_ms": result.duration_ms,
                "details": result.details,
                "error": result.error,
            }
        
        @router.post(
            "/health/run-all",
            summary="Run all health checks",
            description="Manually run all health checks",
            response_description="All health check results",
        )
        async def run_all_health_checks() -> Dict[str, Any]:
            """Run all health checks."""
            # Run all checks
            results = self.health.run_all_checks()
            
            # Convert to dictionary
            result_data = {}
            for check_id, result in results.items():
                result_data[check_id] = {
                    "status": result.status,
                    "timestamp": result.timestamp.isoformat(),
                    "duration_ms": result.duration_ms,
                    "details": result.details,
                    "error": result.error,
                }
            
            # Get overall status
            summary = self.health.get_health_summary()
            
            return {
                "results": result_data,
                "count": len(results),
                "status": summary["status"],
                "counts": summary["counts"],
            }
        
        # Alert routes (only if alert manager is available)
        if self.alerts:
            @router.get(
                "/alerts",
                summary="Get all alerts",
                description="Get all active alerts",
                response_description="List of active alerts",
            )
            async def get_alerts(
                state: Optional[str] = Query(None, description="Filter by alert state"),
                severity: Optional[str] = Query(None, description="Filter by alert severity"),
            ) -> Dict[str, Any]:
                """Get all active alerts."""
                # Filter by state if provided
                alert_state = None
                if state:
                    try:
                        alert_state = AlertState(state)
                    except ValueError:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid alert state: {state}"
                        )
                
                # Get alerts
                alerts = self.alerts.get_alerts(state=alert_state)
                
                # Filter by severity if provided
                if severity:
                    try:
                        alert_severity = AlertSeverity(severity)
                        alerts = [a for a in alerts if a.severity == alert_severity]
                    except ValueError:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid alert severity: {severity}"
                        )
                
                # Convert to dictionary
                alert_data = []
                for alert in alerts:
                    alert_data.append({
                        "id": alert.id,
                        "rule_id": alert.rule_id,
                        "name": alert.name,
                        "description": alert.description,
                        "metric_name": alert.metric_name,
                        "value": alert.value,
                        "threshold": alert.threshold,
                        "comparison": alert.comparison,
                        "severity": alert.severity,
                        "state": alert.state,
                        "labels": alert.labels,
                        "started_at": alert.started_at.isoformat(),
                        "updated_at": alert.updated_at.isoformat(),
                        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
                        "suppressed": alert.suppressed,
                        "notification_count": alert.notification_count,
                    })
                
                return {
                    "alerts": alert_data,
                    "count": len(alert_data)
                }
            
            @router.get(
                "/alerts/{alert_id}",
                summary="Get alert by ID",
                description="Get information about a specific alert",
                response_description="Alert details",
            )
            async def get_alert(alert_id: str) -> Dict[str, Any]:
                """Get a specific alert."""
                alert = self.alerts.get_alert(alert_id)
                if not alert:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Alert not found: {alert_id}"
                    )
                
                # Convert to dictionary
                return {
                    "id": alert.id,
                    "rule_id": alert.rule_id,
                    "name": alert.name,
                    "description": alert.description,
                    "metric_name": alert.metric_name,
                    "value": alert.value,
                    "threshold": alert.threshold,
                    "comparison": alert.comparison,
                    "severity": alert.severity,
                    "state": alert.state,
                    "labels": alert.labels,
                    "started_at": alert.started_at.isoformat(),
                    "updated_at": alert.updated_at.isoformat(),
                    "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
                    "suppressed": alert.suppressed,
                    "suppressed_until": alert.suppressed_until.isoformat() if alert.suppressed_until else None,
                    "suppressed_reason": alert.suppressed_reason,
                    "notified_at": alert.notified_at.isoformat() if alert.notified_at else None,
                    "notification_count": alert.notification_count,
                    "last_value": alert.last_value,
                    "last_checked": alert.last_checked.isoformat(),
                }
            
            @router.get(
                "/alerts/history",
                summary="Get alert history",
                description="Get historical alerts",
                response_description="List of historical alerts",
            )
            async def get_alert_history(
                limit: int = Query(100, description="Maximum number of alerts to return"),
            ) -> Dict[str, Any]:
                """Get alert history."""
                history = self.alerts.get_alert_history(limit=limit)
                
                # Convert to dictionary
                history_data = []
                for alert in history:
                    history_data.append({
                        "id": alert.id,
                        "rule_id": alert.rule_id,
                        "name": alert.name,
                        "severity": alert.severity,
                        "state": alert.state,
                        "started_at": alert.started_at.isoformat(),
                        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
                    })
                
                return {
                    "history": history_data,
                    "count": len(history_data)
                }
            
            @router.get(
                "/alerts/rules",
                summary="Get alert rules",
                description="Get all alert rules",
                response_description="List of alert rules",
            )
            async def get_alert_rules() -> Dict[str, Any]:
                """Get all alert rules."""
                rules = self.alerts.get_rules()
                
                # Convert to dictionary
                rule_data = []
                for rule in rules:
                    rule_data.append({
                        "id": rule.id,
                        "name": rule.name,
                        "description": rule.description,
                        "metric_name": rule.metric_name,
                        "threshold": rule.threshold,
                        "comparison": rule.comparison,
                        "severity": rule.severity,
                        "duration": rule.duration,
                        "enabled": rule.enabled,
                        "labels": rule.labels,
                        "notifications": [n for n in rule.notifications],
                        "auto_resolve": rule.auto_resolve,
                        "resolve_duration": rule.resolve_duration,
                    })
                
                return {
                    "rules": rule_data,
                    "count": len(rule_data)
                }
            
            @router.post(
                "/alerts/check",
                summary="Check alerts",
                description="Manually check all alert rules",
                response_description="Alert check result",
            )
            async def check_alerts() -> Dict[str, Any]:
                """Manually check all alert rules."""
                # Run alert check
                self.alerts.check_alerts()
                
                # Get current alerts
                alerts = self.alerts.get_alerts()
                
                # Count by state and severity
                state_counts = {}
                severity_counts = {}
                
                for alert in alerts:
                    state_counts[alert.state] = state_counts.get(alert.state, 0) + 1
                    severity_counts[alert.severity] = severity_counts.get(alert.severity, 0) + 1
                
                return {
                    "checked_at": datetime.now().isoformat(),
                    "alert_count": len(alerts),
                    "state_counts": state_counts,
                    "severity_counts": severity_counts,
                }
        
        # System info route
        @router.get(
            "/system",
            summary="Get system information",
            description="Get detailed system information",
            response_description="System information",
        )
        async def get_system_info() -> Dict[str, Any]:
            """Get detailed system information."""
            return self.monitoring.get_system_info()
        
        # Dashboard routes
        @router.get(
            "/dashboard",
            summary="Monitoring dashboard",
            description="Monitoring dashboard UI",
            response_class=HTMLResponse,
        )
        async def get_dashboard() -> str:
            """Get monitoring dashboard UI."""
            return """
            <!DOCTYPE html>
            <html>
            <head>
                <title>MCP Monitoring Dashboard</title>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    body {
                        font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                        margin: 0;
                        padding: 20px;
                        color: #333;
                        background-color: #f8f9fa;
                    }
                    .container {
                        max-width: 1200px;
                        margin: 0 auto;
                    }
                    .header {
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                        margin-bottom: 20px;
                        padding-bottom: 10px;
                        border-bottom: 1px solid #dee2e6;
                    }
                    .header h1 {
                        margin: 0;
                        color: #212529;
                    }
                    .card {
                        background-color: #fff;
                        border-radius: 6px;
                        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
                        padding: 16px;
                        margin-bottom: 20px;
                    }
                    .card-header {
                        margin: -16px -16px 16px;
                        padding: 8px 16px;
                        background-color: #f1f3f5;
                        border-top-left-radius: 6px;
                        border-top-right-radius: 6px;
                        border-bottom: 1px solid #e9ecef;
                    }
                    .card-header h2 {
                        margin: 0;
                        font-size: 18px;
                        color: #495057;
                    }
                    .status {
                        display: inline-block;
                        padding: 4px 8px;
                        border-radius: 4px;
                        font-weight: bold;
                    }
                    .status-healthy {
                        background-color: #d4edda;
                        color: #155724;
                    }
                    .status-degraded {
                        background-color: #fff3cd;
                        color: #856404;
                    }
                    .status-unhealthy {
                        background-color: #f8d7da;
                        color: #721c24;
                    }
                    .status-unknown {
                        background-color: #e9ecef;
                        color: #495057;
                    }
                    .metric-row {
                        display: flex;
                        justify-content: space-between;
                        margin-bottom: 8px;
                        padding-bottom: 8px;
                        border-bottom: 1px solid #e9ecef;
                    }
                    .metric-name {
                        font-weight: bold;
                    }
                    .metric-value {
                        font-family: monospace;
                    }
                    .button {
                        display: inline-block;
                        padding: 6px 12px;
                        background-color: #007bff;
                        color: white;
                        border-radius: 4px;
                        text-decoration: none;
                        font-weight: 500;
                        cursor: pointer;
                    }
                    .button:hover {
                        background-color: #0069d9;
                    }
                    .grid {
                        display: grid;
                        grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                        gap: 20px;
                    }
                    #alertsTable, #checksTable {
                        width: 100%;
                        border-collapse: collapse;
                    }
                    #alertsTable th, #alertsTable td, #checksTable th, #checksTable td {
                        padding: 8px;
                        text-align: left;
                        border-bottom: 1px solid #e9ecef;
                    }
                    #alertsTable th, #checksTable th {
                        background-color: #f1f3f5;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>MCP Monitoring Dashboard</h1>
                        <div>
                            <button id="refreshBtn" class="button">Refresh Data</button>
                        </div>
                    </div>
                    
                    <div class="card">
                        <div class="card-header">
                            <h2>System Health</h2>
                        </div>
                        <div id="healthStatus" class="status status-unknown">Unknown</div>
                        <div id="healthDetails"></div>
                        <p></p>
                        <button id="checkHealthBtn" class="button">Run Health Checks</button>
                    </div>
                    
                    <div class="grid">
                        <div class="card">
                            <div class="card-header">
                                <h2>System Metrics</h2>
                            </div>
                            <div id="systemMetrics"></div>
                        </div>
                        
                        <div class="card">
                            <div class="card-header">
                                <h2>Storage Metrics</h2>
                            </div>
                            <div id="storageMetrics"></div>
                        </div>
                    </div>
                    
                    <div class="card">
                        <div class="card-header">
                            <h2>Health Checks</h2>
                        </div>
                        <div id="healthChecks"></div>
                    </div>
                    
                    <div class="card">
                        <div class="card-header">
                            <h2>Active Alerts</h2>
                        </div>
                        <div id="alerts"></div>
                        <p></p>
                        <button id="checkAlertsBtn" class="button">Check Alerts</button>
                    </div>
                </div>
                
                <script>
                    // Fetch health status
                    async function fetchHealth() {
                        try {
                            const response = await fetch('/api/v0/monitoring/health');
                            const data = await response.json();
                            
                            // Update status
                            const statusEl = document.getElementById('healthStatus');
                            statusEl.textContent = data.status.toUpperCase();
                            statusEl.className = `status status-${data.status}`;
                            
                            // Update details
                            const detailsHtml = `
                                <div class="metric-row">
                                    <span class="metric-name">Last Update:</span>
                                    <span class="metric-value">${new Date(data.last_update).toLocaleString()}</span>
                                </div>
                                <div class="metric-row">
                                    <span class="metric-name">Healthy Checks:</span>
                                    <span class="metric-value">${data.counts.healthy || 0}</span>
                                </div>
                                <div class="metric-row">
                                    <span class="metric-name">Degraded Checks:</span>
                                    <span class="metric-value">${data.counts.degraded || 0}</span>
                                </div>
                                <div class="metric-row">
                                    <span class="metric-name">Unhealthy Checks:</span>
                                    <span class="metric-value">${data.counts.unhealthy || 0}</span>
                                </div>
                                <div class="metric-row">
                                    <span class="metric-name">Unknown Checks:</span>
                                    <span class="metric-value">${data.counts.unknown || 0}</span>
                                </div>
                                <div class="metric-row">
                                    <span class="metric-name">Total Checks:</span>
                                    <span class="metric-value">${data.total_checks}</span>
                                </div>
                            `;
                            
                            document.getElementById('healthDetails').innerHTML = detailsHtml;
                        } catch (error) {
                            console.error('Error fetching health:', error);
                            document.getElementById('healthStatus').textContent = 'Error fetching health data';
                            document.getElementById('healthStatus').className = 'status status-unhealthy';
                        }
                    }
                    
                    // Fetch system metrics
                    async function fetchSystemMetrics() {
                        try {
                            const response = await fetch('/api/v0/monitoring/metrics/system');
                            const data = await response.json();
                            
                            let metricsHtml = '';
                            
                            // CPU usage
                            if (data.system_cpu_usage) {
                                const cpuData = data.system_cpu_usage.series;
                                const totalCpu = Object.values(cpuData).find(s => s.labels.cpu === 'total');
                                if (totalCpu) {
                                    metricsHtml += `
                                        <div class="metric-row">
                                            <span class="metric-name">CPU Usage:</span>
                                            <span class="metric-value">${totalCpu.value.toFixed(1)}%</span>
                                        </div>
                                    `;
                                }
                            }
                            
                            // Memory usage
                            if (data.system_memory_usage) {
                                const memoryData = Object.values(data.system_memory_usage.series)[0];
                                if (memoryData) {
                                    const gbValue = (memoryData.value / (1024 * 1024 * 1024)).toFixed(2);
                                    metricsHtml += `
                                        <div class="metric-row">
                                            <span class="metric-name">Memory Usage:</span>
                                            <span class="metric-value">${gbValue} GB</span>
                                        </div>
                                    `;
                                }
                            }
                            
                            // Disk usage
                            if (data.system_disk_usage) {
                                const diskData = Object.values(data.system_disk_usage.series);
                                for (const disk of diskData) {
                                    const path = disk.labels.path;
                                    const gbValue = (disk.value / (1024 * 1024 * 1024)).toFixed(2);
                                    metricsHtml += `
                                        <div class="metric-row">
                                            <span class="metric-name">Disk Usage (${path}):</span>
                                            <span class="metric-value">${gbValue} GB</span>
                                        </div>
                                    `;
                                }
                            }
                            
                            // Network
                            if (data.network_bytes_sent) {
                                const networkData = Object.values(data.network_bytes_sent.series);
                                for (const net of networkData) {
                                    const interface = net.labels.interface;
                                    const mbValue = (net.value / (1024 * 1024)).toFixed(2);
                                    metricsHtml += `
                                        <div class="metric-row">
                                            <span class="metric-name">Network Sent (${interface}):</span>
                                            <span class="metric-value">${mbValue} MB</span>
                                        </div>
                                    `;
                                }
                            }
                            
                            document.getElementById('systemMetrics').innerHTML = metricsHtml;
                        } catch (error) {
                            console.error('Error fetching system metrics:', error);
                            document.getElementById('systemMetrics').innerHTML = 'Error fetching system metrics';
                        }
                    }
                    
                    // Fetch storage metrics
                    async function fetchStorageMetrics() {
                        try {
                            const response = await fetch('/api/v0/monitoring/metrics/backend');
                            const data = await response.json();
                            
                            let metricsHtml = '';
                            
                            // Backend stored bytes
                            if (data.backend_stored_bytes) {
                                const storageData = Object.values(data.backend_stored_bytes.series);
                                for (const storage of storageData) {
                                    const backend = storage.labels.backend;
                                    const mbValue = (storage.value / (1024 * 1024)).toFixed(2);
                                    metricsHtml += `
                                        <div class="metric-row">
                                            <span class="metric-name">${backend} Storage:</span>
                                            <span class="metric-value">${mbValue} MB</span>
                                        </div>
                                    `;
                                }
                            }
                            
                            // Backend operations
                            if (data.backend_operations_total) {
                                const opsData = Object.values(data.backend_operations_total.series);
                                const backendOps = {};
                                
                                for (const op of opsData) {
                                    const backend = op.labels.backend;
                                    const operation = op.labels.operation;
                                    const status = op.labels.status;
                                    
                                    if (!backendOps[backend]) {
                                        backendOps[backend] = { total: 0 };
                                    }
                                    
                                    backendOps[backend][`${operation}_${status}`] = op.value;
                                    backendOps[backend].total += op.value;
                                }
                                
                                for (const [backend, ops] of Object.entries(backendOps)) {
                                    metricsHtml += `
                                        <div class="metric-row">
                                            <span class="metric-name">${backend} Operations:</span>
                                            <span class="metric-value">${ops.total}</span>
                                        </div>
                                    `;
                                }
                            }
                            
                            document.getElementById('storageMetrics').innerHTML = metricsHtml || 'No storage metrics available';
                        } catch (error) {
                            console.error('Error fetching storage metrics:', error);
                            document.getElementById('storageMetrics').innerHTML = 'Error fetching storage metrics';
                        }
                    }
                    
                    // Fetch health checks
                    async function fetchHealthChecks() {
                        try {
                            const response = await fetch('/api/v0/monitoring/health/checks');
                            const data = await response.json();
                            
                            let checksHtml = '<table id="checksTable"><thead><tr><th>Name</th><th>Type</th><th>Status</th><th>Last Run</th><th>Actions</th></tr></thead><tbody>';
                            
                            // Fetch check results
                            const resultsResponse = await fetch('/api/v0/monitoring/health');
                            const resultsData = await resultsResponse.json();
                            
                            // Process checks
                            for (const [id, check] of Object.entries(data.checks)) {
                                // Get result for this check
                                const checkResponse = await fetch(`/api/v0/monitoring/health/checks/${id}`);
                                const checkData = await checkResponse.json();
                                const result = checkData.latest_result;
                                
                                let status = 'Unknown';
                                let statusClass = 'status-unknown';
                                let lastRun = 'Never';
                                
                                if (result) {
                                    status = result.status.charAt(0).toUpperCase() + result.status.slice(1);
                                    statusClass = `status-${result.status}`;
                                    lastRun = new Date(result.timestamp).toLocaleString();
                                }
                                
                                checksHtml += `
                                    <tr>
                                        <td>${check.name}</td>
                                        <td>${check.check_type}: ${check.target}</td>
                                        <td><span class="status ${statusClass}">${status}</span></td>
                                        <td>${lastRun}</td>
                                        <td><button class="button" onclick="runSingleHealthCheck('${id}')">Run</button></td>
                                    </tr>
                                `;
                            }
                            
                            checksHtml += '</tbody></table>';
                            document.getElementById('healthChecks').innerHTML = checksHtml;
                        } catch (error) {
                            console.error('Error fetching health checks:', error);
                            document.getElementById('healthChecks').innerHTML = 'Error fetching health checks';
                        }
                    }
                    
                    // Fetch alerts
                    async function fetchAlerts() {
                        try {
                            const response = await fetch('/api/v0/monitoring/alerts');
                            const data = await response.json();
                            
                            if (data.alerts && data.alerts.length > 0) {
                                let alertsHtml = '<table id="alertsTable"><thead><tr><th>Name</th><th>Severity</th><th>State</th><th>Value</th><th>Threshold</th><th>Started</th></tr></thead><tbody>';
                                
                                for (const alert of data.alerts) {
                                    const severity = alert.severity.toUpperCase();
                                    const state = alert.state.charAt(0).toUpperCase() + alert.state.slice(1);
                                    const started = new Date(alert.started_at).toLocaleString();
                                    
                                    let severityClass = '';
                                    if (alert.severity === 'critical') severityClass = 'status-unhealthy';
                                    else if (alert.severity === 'warning') severityClass = 'status-degraded';
                                    else if (alert.severity === 'info') severityClass = 'status-healthy';
                                    
                                    let stateClass = '';
                                    if (alert.state === 'firing') stateClass = 'status-unhealthy';
                                    else if (alert.state === 'resolved') stateClass = 'status-healthy';
                                    else if (alert.state === 'pending') stateClass = 'status-unknown';
                                    
                                    alertsHtml += `
                                        <tr>
                                            <td>${alert.name}</td>
                                            <td><span class="status ${severityClass}">${severity}</span></td>
                                            <td><span class="status ${stateClass}">${state}</span></td>
                                            <td>${alert.value}</td>
                                            <td>${alert.threshold} (${alert.comparison})</td>
                                            <td>${started}</td>
                                        </tr>
                                    `;
                                }
                                
                                alertsHtml += '</tbody></table>';
                                document.getElementById('alerts').innerHTML = alertsHtml;
                            } else {
                                document.getElementById('alerts').innerHTML = '<p>No active alerts.</p>';
                            }
                        } catch (error) {
                            console.error('Error fetching alerts:', error);
                            document.getElementById('alerts').innerHTML = 'Error fetching alerts';
                        }
                    }
                    
                    // Run all health checks
                    async function runAllHealthChecks() {
                        try {
                            document.getElementById('checkHealthBtn').textContent = 'Running...';
                            document.getElementById('checkHealthBtn').disabled = true;
                            
                            const response = await fetch('/api/v0/monitoring/health/run-all', {
                                method: 'POST'
                            });
                            
                            await fetchHealth();
                            await fetchHealthChecks();
                            
                            document.getElementById('checkHealthBtn').textContent = 'Run Health Checks';
                            document.getElementById('checkHealthBtn').disabled = false;
                        } catch (error) {
                            console.error('Error running health checks:', error);
                            document.getElementById('checkHealthBtn').textContent = 'Run Health Checks';
                            document.getElementById('checkHealthBtn').disabled = false;
                        }
                    }
                    
                    // Run single health check
                    async function runSingleHealthCheck(id) {
                        try {
                            const response = await fetch(`/api/v0/monitoring/health/checks/${id}/run`, {
                                method: 'POST'
                            });
                            
                            // Refresh data
                            await fetchHealth();
                            await fetchHealthChecks();
                        } catch (error) {
                            console.error(`Error running health check ${id}:`, error);
                        }
                    }
                    
                    // Check alerts
                    async function checkAlerts() {
                        try {
                            document.getElementById('checkAlertsBtn').textContent = 'Checking...';
                            document.getElementById('checkAlertsBtn').disabled = true;
                            
                            const response = await fetch('/api/v0/monitoring/alerts/check', {
                                method: 'POST'
                            });
                            
                            await fetchAlerts();
                            
                            document.getElementById('checkAlertsBtn').textContent = 'Check Alerts';
                            document.getElementById('checkAlertsBtn').disabled = false;
                        } catch (error) {
                            console.error('Error checking alerts:', error);
                            document.getElementById('checkAlertsBtn').textContent = 'Check Alerts';
                            document.getElementById('checkAlertsBtn').disabled = false;
                        }
                    }
                    
                    // Refresh all data
                    async function refreshAllData() {
                        document.getElementById('refreshBtn').textContent = 'Refreshing...';
                        document.getElementById('refreshBtn').disabled = true;
                        
                        await Promise.all([
                            fetchHealth(),
                            fetchSystemMetrics(),
                            fetchStorageMetrics(),
                            fetchHealthChecks(),
                            fetchAlerts()
                        ]);
                        
                        document.getElementById('refreshBtn').textContent = 'Refresh Data';
                        document.getElementById('refreshBtn').disabled = false;
                    }
                    
                    // Add event listeners
                    document.addEventListener('DOMContentLoaded', function() {
                        // Initial data load
                        refreshAllData();
                        
                        // Button event listeners
                        document.getElementById('refreshBtn').addEventListener('click', refreshAllData);
                        document.getElementById('checkHealthBtn').addEventListener('click', runAllHealthChecks);
                        document.getElementById('checkAlertsBtn').addEventListener('click', checkAlerts);
                        
                        // Make global functions available
                        window.runSingleHealthCheck = runSingleHealthCheck;
                    });
                </script>
            </body>
            </html>
            """


# Create monitoring API service
def create_monitoring_api(
    monitoring_manager: MonitoringManager,
    prometheus_integration: PrometheusIntegration,
    health_manager: HealthCheckManager,
    alert_manager: Optional[AlertManager] = None,
) -> MonitoringAPIService:
    """
    Create the monitoring API service.
    
    Args:
        monitoring_manager: MCP monitoring manager
        prometheus_integration: Prometheus integration
        health_manager: Health check manager
        alert_manager: Optional alert manager
        
    Returns:
        MonitoringAPIService instance
    """
    return MonitoringAPIService(
        monitoring_manager=monitoring_manager,
        prometheus_integration=prometheus_integration,
        health_manager=health_manager,
        alert_manager=alert_manager,
    )
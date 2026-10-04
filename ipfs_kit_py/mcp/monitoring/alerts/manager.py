"""
Alert Management System for MCP Server

This module provides alerting capabilities for metric thresholds and health checks
as specified in the MCP roadmap for Phase 1: Core Functionality Enhancements (Q3 2025).

Key features:
- Configurable alert rules for metrics
- Multiple notification channels (email, webhook, syslog)
- Alert status tracking and history
- Alert suppression and grouping
"""

import os
import re
import time
import json
import smtplib
import logging
import threading
import requests
import socket
from enum import Enum
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List, Optional, Set, Union, Callable, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from ..monitoring import MonitoringManager, MetricTag, MetricType

# Configure logging
logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertState(str, Enum):
    """Alert states."""
    PENDING = "pending"  # Initial detection, not yet triggered
    FIRING = "firing"    # Actively firing
    RESOLVED = "resolved"  # Was firing but now resolved
    SUPPRESSED = "suppressed"  # Suppressed by configuration


class NotificationType(str, Enum):
    """Types of alert notifications."""
    EMAIL = "email"
    WEBHOOK = "webhook"
    SYSLOG = "syslog"
    LOG = "log"
    COMMAND = "command"


@dataclass
class AlertRule:
    """Definition of an alert rule."""
    id: str
    name: str
    description: str
    metric_name: str
    threshold: float
    duration: int  # seconds threshold must be exceeded
    severity: AlertSeverity
    comparison: str  # "gt", "lt", "eq", "ne", "ge", "le"
    labels: Dict[str, str] = field(default_factory=dict)
    notifications: List[NotificationType] = field(default_factory=list)
    enabled: bool = True
    auto_resolve: bool = True
    resolve_duration: int = 300  # seconds below threshold to auto-resolve
    suppress_repeat: int = 3600  # seconds between repeated notifications
    repeat_interval: int = 0  # seconds between repeat notifications (0 = no repeat)
    group_by: List[str] = field(default_factory=list)  # label keys to group by


@dataclass
class Alert:
    """An instance of a triggered alert."""
    id: str
    rule_id: str
    name: str
    description: str
    metric_name: str
    threshold: float
    severity: AlertSeverity
    comparison: str
    value: float
    state: AlertState
    labels: Dict[str, str]
    started_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    suppressed: bool = False
    suppressed_until: Optional[datetime] = None
    suppressed_reason: Optional[str] = None
    notified_at: Optional[datetime] = None
    notification_count: int = 0
    last_value: float = 0
    last_checked: datetime = field(default_factory=datetime.now)


class NotificationManager:
    """
    Manager for alert notifications.
    
    This class handles sending notifications through different channels.
    """
    
    def __init__(self):
        """Initialize the notification manager."""
        self.email_config = {
            "enabled": False,
            "server": "localhost",
            "port": 25,
            "use_tls": False,
            "use_ssl": False,
            "username": None,
            "password": None,
            "from_addr": "mcp-alerts@localhost",
            "to_addrs": [],
            "subject_prefix": "[MCP Alert]",
        }
        
        self.webhook_config = {
            "enabled": False,
            "url": None,
            "method": "POST",
            "headers": {},
            "timeout": 10,
        }
        
        self.syslog_config = {
            "enabled": False,
            "facility": "local0",
            "server": "localhost",
            "port": 514,
            "protocol": "udp",
            "tag": "mcp-alerts",
        }
        
        self.command_config = {
            "enabled": False,
            "command": None,
            "shell": True,
            "timeout": 30,
        }
        
        self.log_config = {
            "enabled": True,
            "level": "warning",
        }
    
    def configure_email(
        self,
        enabled: bool = False,
        server: str = "localhost",
        port: int = 25,
        use_tls: bool = False,
        use_ssl: bool = False,
        username: Optional[str] = None,
        password: Optional[str] = None,
        from_addr: str = "mcp-alerts@localhost",
        to_addrs: List[str] = None,
        subject_prefix: str = "[MCP Alert]",
    ) -> None:
        """
        Configure email notifications.
        
        Args:
            enabled: Whether email notifications are enabled
            server: SMTP server hostname
            port: SMTP server port
            use_tls: Whether to use STARTTLS
            use_ssl: Whether to use SSL/TLS
            username: SMTP username
            password: SMTP password
            from_addr: Sender email address
            to_addrs: List of recipient email addresses
            subject_prefix: Prefix for email subjects
        """
        self.email_config = {
            "enabled": enabled,
            "server": server,
            "port": port,
            "use_tls": use_tls,
            "use_ssl": use_ssl,
            "username": username,
            "password": password,
            "from_addr": from_addr,
            "to_addrs": to_addrs or [],
            "subject_prefix": subject_prefix,
        }
    
    def configure_webhook(
        self,
        enabled: bool = False,
        url: Optional[str] = None,
        method: str = "POST",
        headers: Dict[str, str] = None,
        timeout: int = 10,
    ) -> None:
        """
        Configure webhook notifications.
        
        Args:
            enabled: Whether webhook notifications are enabled
            url: Webhook URL
            method: HTTP method (GET or POST)
            headers: HTTP headers
            timeout: Request timeout in seconds
        """
        self.webhook_config = {
            "enabled": enabled,
            "url": url,
            "method": method,
            "headers": headers or {},
            "timeout": timeout,
        }
    
    def configure_syslog(
        self,
        enabled: bool = False,
        facility: str = "local0",
        server: str = "localhost",
        port: int = 514,
        protocol: str = "udp",
        tag: str = "mcp-alerts",
    ) -> None:
        """
        Configure syslog notifications.
        
        Args:
            enabled: Whether syslog notifications are enabled
            facility: Syslog facility
            server: Syslog server hostname
            port: Syslog server port
            protocol: Protocol (udp or tcp)
            tag: Syslog tag
        """
        self.syslog_config = {
            "enabled": enabled,
            "facility": facility,
            "server": server,
            "port": port,
            "protocol": protocol,
            "tag": tag,
        }
    
    def configure_command(
        self,
        enabled: bool = False,
        command: Optional[str] = None,
        shell: bool = True,
        timeout: int = 30,
    ) -> None:
        """
        Configure command notifications.
        
        Args:
            enabled: Whether command notifications are enabled
            command: Command to execute
            shell: Whether to use shell
            timeout: Command timeout in seconds
        """
        self.command_config = {
            "enabled": enabled,
            "command": command,
            "shell": shell,
            "timeout": timeout,
        }
    
    def configure_log(
        self,
        enabled: bool = True,
        level: str = "warning",
    ) -> None:
        """
        Configure log notifications.
        
        Args:
            enabled: Whether log notifications are enabled
            level: Log level
        """
        self.log_config = {
            "enabled": enabled,
            "level": level,
        }
    
    def send_notification(
        self, 
        alert: Alert,
        notification_types: Optional[List[NotificationType]] = None,
    ) -> bool:
        """
        Send notifications for an alert.
        
        Args:
            alert: Alert to notify about
            notification_types: Types of notifications to send (all if None)
            
        Returns:
            True if any notification was sent
        """
        if not notification_types:
            notification_types = [
                NotificationType.EMAIL,
                NotificationType.WEBHOOK,
                NotificationType.SYSLOG,
                NotificationType.LOG,
                NotificationType.COMMAND,
            ]
        
        success = False
        
        # Send notifications based on types
        for notification_type in notification_types:
            if notification_type == NotificationType.EMAIL and self.email_config["enabled"]:
                if self._send_email_notification(alert):
                    success = True
            
            elif notification_type == NotificationType.WEBHOOK and self.webhook_config["enabled"]:
                if self._send_webhook_notification(alert):
                    success = True
            
            elif notification_type == NotificationType.SYSLOG and self.syslog_config["enabled"]:
                if self._send_syslog_notification(alert):
                    success = True
            
            elif notification_type == NotificationType.LOG and self.log_config["enabled"]:
                if self._send_log_notification(alert):
                    success = True
            
            elif notification_type == NotificationType.COMMAND and self.command_config["enabled"]:
                if self._send_command_notification(alert):
                    success = True
        
        return success
    
    def _send_email_notification(self, alert: Alert) -> bool:
        """
        Send email notification for an alert.
        
        Args:
            alert: Alert to notify about
            
        Returns:
            True if notification was sent
        """
        if not self.email_config["enabled"] or not self.email_config["to_addrs"]:
            return False
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg["From"] = self.email_config["from_addr"]
            msg["To"] = ", ".join(self.email_config["to_addrs"])
            
            # Build subject based on severity and state
            severity_prefix = f"[{alert.severity}]"
            state_suffix = f"({alert.state})"
            
            msg["Subject"] = f"{self.email_config['subject_prefix']} {severity_prefix} {alert.name} {state_suffix}"
            
            # Build email body
            body = f"""
Alert: {alert.name}
Description: {alert.description}
Severity: {alert.severity}
State: {alert.state}
Metric: {alert.metric_name}
Value: {alert.value} (threshold: {alert.threshold} {alert.comparison})
Started: {alert.started_at.isoformat()}
Updated: {alert.updated_at.isoformat()}
"""
            
            if alert.resolved_at:
                body += f"\nResolved: {alert.resolved_at.isoformat()}"
            
            if alert.labels:
                body += "\n\nLabels:\n"
                for key, value in alert.labels.items():
                    body += f"  {key}: {value}\n"
            
            msg.attach(MIMEText(body, "plain"))
            
            # Connect to SMTP server
            if self.email_config["use_ssl"]:
                smtp = smtplib.SMTP_SSL(
                    self.email_config["server"],
                    self.email_config["port"]
                )
            else:
                smtp = smtplib.SMTP(
                    self.email_config["server"],
                    self.email_config["port"]
                )
            
            # Use TLS if configured
            if self.email_config["use_tls"]:
                smtp.starttls()
            
            # Login if credentials provided
            if self.email_config["username"] and self.email_config["password"]:
                smtp.login(
                    self.email_config["username"],
                    self.email_config["password"]
                )
            
            # Send email
            smtp.send_message(msg)
            smtp.quit()
            
            logger.info(f"Sent email notification for alert {alert.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email notification for alert {alert.id}: {e}")
            return False
    
    def _send_webhook_notification(self, alert: Alert) -> bool:
        """
        Send webhook notification for an alert.
        
        Args:
            alert: Alert to notify about
            
        Returns:
            True if notification was sent
        """
        if not self.webhook_config["enabled"] or not self.webhook_config["url"]:
            return False
        
        try:
            # Create alert payload
            payload = {
                "id": alert.id,
                "rule_id": alert.rule_id,
                "name": alert.name,
                "description": alert.description,
                "severity": alert.severity,
                "state": alert.state,
                "metric_name": alert.metric_name,
                "value": alert.value,
                "threshold": alert.threshold,
                "comparison": alert.comparison,
                "labels": alert.labels,
                "started_at": alert.started_at.isoformat(),
                "updated_at": alert.updated_at.isoformat(),
            }
            
            if alert.resolved_at:
                payload["resolved_at"] = alert.resolved_at.isoformat()
            
            # Send request
            method = self.webhook_config["method"].upper()
            timeout = self.webhook_config["timeout"]
            
            if method == "POST":
                response = requests.post(
                    self.webhook_config["url"],
                    json=payload,
                    headers=self.webhook_config["headers"],
                    timeout=timeout
                )
            else:
                response = requests.get(
                    self.webhook_config["url"],
                    params=payload,
                    headers=self.webhook_config["headers"],
                    timeout=timeout
                )
            
            if response.status_code >= 200 and response.status_code < 300:
                logger.info(f"Sent webhook notification for alert {alert.id}")
                return True
            else:
                logger.warning(
                    f"Webhook notification failed for alert {alert.id}: "
                    f"Status {response.status_code} - {response.text}"
                )
                return False
            
        except Exception as e:
            logger.error(f"Failed to send webhook notification for alert {alert.id}: {e}")
            return False
    
    def _send_syslog_notification(self, alert: Alert) -> bool:
        """
        Send syslog notification for an alert.
        
        Args:
            alert: Alert to notify about
            
        Returns:
            True if notification was sent
        """
        if not self.syslog_config["enabled"]:
            return False
        
        try:
            # Format syslog message
            tag = self.syslog_config["tag"]
            priority = self._get_syslog_priority(alert.severity, self.syslog_config["facility"])
            
            # Format timestamp for syslog (RFC3339)
            timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            
            # Build message content
            hostname = socket.gethostname()
            msg_content = f"[{alert.severity}] [{alert.state}] {alert.name}: {alert.description} (value={alert.value}, threshold={alert.threshold})"
            
            # Format according to RFC5424
            message = f"<{priority}>{timestamp} {hostname} {tag} - - - {msg_content}"
            
            # Create socket and send message
            if self.syslog_config["protocol"].lower() == "tcp":
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5.0)
                sock.connect((self.syslog_config["server"], self.syslog_config["port"]))
                sock.send(message.encode("utf-8"))
                sock.close()
            else:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.sendto(
                    message.encode("utf-8"),
                    (self.syslog_config["server"], self.syslog_config["port"])
                )
            
            logger.info(f"Sent syslog notification for alert {alert.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send syslog notification for alert {alert.id}: {e}")
            return False
    
    def _get_syslog_priority(self, severity: AlertSeverity, facility: str) -> int:
        """
        Get syslog priority value based on severity and facility.
        
        Args:
            severity: Alert severity
            facility: Syslog facility
            
        Returns:
            Syslog priority value
        """
        # Facility codes
        facility_map = {
            "kern": 0,
            "user": 1,
            "mail": 2,
            "daemon": 3,
            "auth": 4,
            "syslog": 5,
            "lpr": 6,
            "news": 7,
            "uucp": 8,
            "cron": 9,
            "authpriv": 10,
            "ftp": 11,
            "ntp": 12,
            "security": 13,
            "console": 14,
            "local0": 16,
            "local1": 17,
            "local2": 18,
            "local3": 19,
            "local4": 20,
            "local5": 21,
            "local6": 22,
            "local7": 23,
        }
        
        # Severity codes
        severity_map = {
            AlertSeverity.INFO: 6,
            AlertSeverity.WARNING: 4,
            AlertSeverity.ERROR: 3,
            AlertSeverity.CRITICAL: 2,
        }
        
        facility_code = facility_map.get(facility.lower(), 16)  # Default to local0
        severity_code = severity_map.get(severity, 6)  # Default to info
        
        # Calculate priority (facility * 8 + severity)
        return (facility_code * 8) + severity_code
    
    def _send_log_notification(self, alert: Alert) -> bool:
        """
        Send log notification for an alert.
        
        Args:
            alert: Alert to notify about
            
        Returns:
            True if notification was sent
        """
        if not self.log_config["enabled"]:
            return False
        
        try:
            # Map severity to log level
            level_map = {
                AlertSeverity.INFO: logging.INFO,
                AlertSeverity.WARNING: logging.WARNING,
                AlertSeverity.ERROR: logging.ERROR,
                AlertSeverity.CRITICAL: logging.CRITICAL,
            }
            
            level = level_map.get(alert.severity, logging.WARNING)
            
            # Format message
            message = (
                f"Alert [{alert.severity}] [{alert.state}] {alert.name}: {alert.description} "
                f"(metric={alert.metric_name}, value={alert.value}, threshold={alert.threshold})"
            )
            
            # Log message at appropriate level
            logger.log(level, message)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send log notification for alert {alert.id}: {e}")
            return False
    
    def _send_command_notification(self, alert: Alert) -> bool:
        """
        Send command notification for an alert.
        
        Args:
            alert: Alert to notify about
            
        Returns:
            True if notification was sent
        """
        if not self.command_config["enabled"] or not self.command_config["command"]:
            return False
        
        try:
            import subprocess
            import shlex
            
            # Prepare environment with alert data
            env = os.environ.copy()
            env["ALERT_ID"] = alert.id
            env["ALERT_NAME"] = alert.name
            env["ALERT_DESCRIPTION"] = alert.description
            env["ALERT_SEVERITY"] = alert.severity
            env["ALERT_STATE"] = alert.state
            env["ALERT_METRIC"] = alert.metric_name
            env["ALERT_VALUE"] = str(alert.value)
            env["ALERT_THRESHOLD"] = str(alert.threshold)
            env["ALERT_COMPARISON"] = alert.comparison
            env["ALERT_STARTED_AT"] = alert.started_at.isoformat()
            env["ALERT_UPDATED_AT"] = alert.updated_at.isoformat()
            
            if alert.resolved_at:
                env["ALERT_RESOLVED_AT"] = alert.resolved_at.isoformat()
            
            # Include labels
            for key, value in alert.labels.items():
                env[f"ALERT_LABEL_{key.upper()}"] = str(value)
            
            # Execute command
            command = self.command_config["command"]
            shell = self.command_config["shell"]
            timeout = self.command_config["timeout"]
            
            if shell:
                subprocess.run(
                    command,
                    shell=True,
                    env=env,
                    timeout=timeout,
                    check=False
                )
            else:
                args = shlex.split(command)
                subprocess.run(
                    args,
                    shell=False,
                    env=env,
                    timeout=timeout,
                    check=False
                )
            
            logger.info(f"Sent command notification for alert {alert.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send command notification for alert {alert.id}: {e}")
            return False


class AlertManager:
    """
    Manager for alert rules and instances.
    
    This class handles alert rule configuration, evaluation, and notification.
    """
    
    def __init__(
        self,
        monitoring_manager: MonitoringManager,
        notification_manager: Optional[NotificationManager] = None,
    ):
        """
        Initialize the alert manager.
        
        Args:
            monitoring_manager: MCP monitoring manager
            notification_manager: Optional notification manager
        """
        self.monitoring = monitoring_manager
        self.notifications = notification_manager or NotificationManager()
        
        # Alert rules by ID
        self.rules: Dict[str, AlertRule] = {}
        
        # Active alerts by ID
        self.alerts: Dict[str, Alert] = {}
        
        # Alert history (resolved alerts)
        self.alert_history: List[Alert] = []
        self.max_history = 1000
        
        # Lock for thread safety
        self.lock = threading.RLock()
        
        # Background thread for alert checking
        self.check_thread = None
        self.running = False
        self.check_interval = 30  # seconds
    
    def add_rule(self, rule: AlertRule) -> None:
        """
        Add an alert rule.
        
        Args:
            rule: Alert rule to add
        """
        with self.lock:
            # Validate rule
            if not rule.id:
                rule.id = f"rule_{int(time.time())}_{len(self.rules)}"
            
            # Check comparison is valid
            if rule.comparison not in ["gt", "lt", "eq", "ne", "ge", "le"]:
                raise ValueError(f"Invalid comparison: {rule.comparison}")
            
            # Add rule
            self.rules[rule.id] = rule
            logger.info(f"Added alert rule {rule.id}: {rule.name}")
    
    def add_rules_from_config(self, config: List[Dict[str, Any]]) -> None:
        """
        Add alert rules from configuration dictionary.
        
        Args:
            config: List of rule configuration dictionaries
        """
        for rule_config in config:
            try:
                # Convert dictionary to AlertRule
                rule = AlertRule(
                    id=rule_config.get("id", f"rule_{int(time.time())}_{len(self.rules)}"),
                    name=rule_config["name"],
                    description=rule_config.get("description", ""),
                    metric_name=rule_config["metric_name"],
                    threshold=float(rule_config["threshold"]),
                    duration=int(rule_config.get("duration", 0)),
                    severity=AlertSeverity(rule_config.get("severity", "warning")),
                    comparison=rule_config["comparison"],
                    labels=rule_config.get("labels", {}),
                    notifications=[NotificationType(n) for n in rule_config.get("notifications", ["log"])],
                    enabled=rule_config.get("enabled", True),
                    auto_resolve=rule_config.get("auto_resolve", True),
                    resolve_duration=int(rule_config.get("resolve_duration", 300)),
                    suppress_repeat=int(rule_config.get("suppress_repeat", 3600)),
                    repeat_interval=int(rule_config.get("repeat_interval", 0)),
                    group_by=rule_config.get("group_by", []),
                )
                
                # Add rule
                self.add_rule(rule)
                
            except Exception as e:
                logger.error(f"Error adding rule from config: {e}")
    
    def remove_rule(self, rule_id: str) -> bool:
        """
        Remove an alert rule.
        
        Args:
            rule_id: ID of the rule to remove
            
        Returns:
            True if rule was removed
        """
        with self.lock:
            if rule_id in self.rules:
                del self.rules[rule_id]
                logger.info(f"Removed alert rule {rule_id}")
                return True
            
            return False
    
    def get_rule(self, rule_id: str) -> Optional[AlertRule]:
        """
        Get an alert rule by ID.
        
        Args:
            rule_id: ID of the rule to get
            
        Returns:
            Alert rule or None if not found
        """
        with self.lock:
            return self.rules.get(rule_id)
    
    def get_rules(self) -> List[AlertRule]:
        """
        Get all alert rules.
        
        Returns:
            List of alert rules
        """
        with self.lock:
            return list(self.rules.values())
    
    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """
        Get an active alert by ID.
        
        Args:
            alert_id: ID of the alert to get
            
        Returns:
            Alert or None if not found
        """
        with self.lock:
            return self.alerts.get(alert_id)
    
    def get_alerts(self, state: Optional[AlertState] = None) -> List[Alert]:
        """
        Get all active alerts, optionally filtered by state.
        
        Args:
            state: Optional state to filter by
            
        Returns:
            List of alerts
        """
        with self.lock:
            if state:
                return [a for a in self.alerts.values() if a.state == state]
            
            return list(self.alerts.values())
    
    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """
        Get resolved alert history.
        
        Args:
            limit: Maximum number of alerts to return
            
        Returns:
            List of historical alerts
        """
        with self.lock:
            return self.alert_history[:limit]
    
    def start(self, interval: int = 30) -> None:
        """
        Start background alert checking.
        
        Args:
            interval: Check interval in seconds
        """
        if self.running:
            return
        
        self.check_interval = interval
        self.running = True
        
        self.check_thread = threading.Thread(
            target=self._check_loop,
            daemon=True
        )
        self.check_thread.start()
        
        logger.info(f"Started alert checking every {interval} seconds")
    
    def stop(self) -> None:
        """Stop background alert checking."""
        self.running = False
        
        if self.check_thread:
            self.check_thread.join(timeout=5.0)
            logger.info("Stopped alert checking")
    
    def check_alerts(self) -> None:
        """Check all alert rules against current metrics."""
        with self.lock:
            try:
                # Check each rule
                for rule_id, rule in self.rules.items():
                    if not rule.enabled:
                        continue
                    
                    try:
                        self._check_rule(rule)
                    except Exception as e:
                        logger.error(f"Error checking rule {rule_id}: {e}")
                
                # Check for auto-resolution of alerts
                self._check_auto_resolution()
                
                # Check for repeat notifications
                self._check_repeat_notifications()
                
            except Exception as e:
                logger.error(f"Error checking alerts: {e}")
    
    def _check_rule(self, rule: AlertRule) -> None:
        """
        Check a single alert rule against current metrics.
        
        Args:
            rule: Alert rule to check
        """
        # Get metrics for this rule
        metric_values = self._get_metric_values(rule.metric_name)
        
        # If no values, nothing to check
        if not metric_values:
            return
        
        # Check each metric value
        for labels, value in metric_values.items():
            # Skip if value is None
            if value is None:
                continue
            
            # Check if metric matches the rule
            matches = self._compare_value(value, rule.threshold, rule.comparison)
            
            # Get alert group key based on group_by labels
            group_key = self._get_alert_group_key(rule, labels)
            
            # Generate alert ID based on rule and labels
            alert_id = f"{rule.id}_{group_key}"
            
            # Check if alert already exists
            if alert_id in self.alerts:
                # Update existing alert
                alert = self.alerts[alert_id]
                
                # Update last checked and value
                alert.last_checked = datetime.now()
                alert.last_value = value
                
                if matches:
                    # Condition still matches
                    if alert.state == AlertState.PENDING:
                        # Check if duration threshold reached
                        duration = (datetime.now() - alert.started_at).total_seconds()
                        
                        if duration >= rule.duration:
                            # Transition to firing
                            alert.state = AlertState.FIRING
                            alert.updated_at = datetime.now()
                            
                            # Send notification
                            self._notify_alert(alert, rule.notifications)
                    
                    elif alert.state == AlertState.RESOLVED:
                        # Alert is matching again after being resolved
                        alert.state = AlertState.FIRING
                        alert.updated_at = datetime.now()
                        alert.resolved_at = None
                        
                        # Send notification for re-firing
                        self._notify_alert(alert, rule.notifications)
                    
                else:
                    # Condition no longer matches
                    if alert.state == AlertState.FIRING:
                        # Auto-resolve if enabled
                        if rule.auto_resolve:
                            # Check resolve duration
                            if rule.resolve_duration > 0:
                                # Mark potential resolution time
                                if not hasattr(alert, "_potential_resolve_time"):
                                    alert._potential_resolve_time = datetime.now()
                            else:
                                # Immediately resolve
                                self._resolve_alert(alert)
                
            elif matches:
                # Create new alert
                now = datetime.now()
                
                # Parse label_values from string
                parsed_labels = {}
                if isinstance(labels, str):
                    try:
                        # Extract key-value pairs from string like "key1:value1_key2:value2"
                        parts = labels.split("_")
                        for part in parts:
                            if ":" in part:
                                k, v = part.split(":", 1)
                                parsed_labels[k] = v
                    except Exception:
                        # Use string as-is if parsing fails
                        parsed_labels = {"series": labels}
                else:
                    parsed_labels = labels if isinstance(labels, dict) else {}
                
                # Merge with rule labels
                alert_labels = {**rule.labels, **parsed_labels}
                
                # Create alert
                alert = Alert(
                    id=alert_id,
                    rule_id=rule.id,
                    name=rule.name,
                    description=rule.description,
                    metric_name=rule.metric_name,
                    threshold=rule.threshold,
                    severity=rule.severity,
                    comparison=rule.comparison,
                    value=value,
                    state=AlertState.PENDING if rule.duration > 0 else AlertState.FIRING,
                    labels=alert_labels,
                    started_at=now,
                    updated_at=now,
                    last_value=value,
                )
                
                # Add alert
                self.alerts[alert_id] = alert
                
                # Send notification if firing (no duration threshold)
                if alert.state == AlertState.FIRING:
                    self._notify_alert(alert, rule.notifications)
    
    def _check_auto_resolution(self) -> None:
        """Check for alerts that should be auto-resolved."""
        for alert_id, alert in list(self.alerts.items()):
            if not hasattr(alert, "_potential_resolve_time"):
                continue
            
            # Get rule
            rule = self.rules.get(alert.rule_id)
            if not rule:
                continue
            
            # Check if resolve duration reached
            potential_resolve_time = getattr(alert, "_potential_resolve_time")
            duration = (datetime.now() - potential_resolve_time).total_seconds()
            
            if duration >= rule.resolve_duration:
                # Resolve alert
                self._resolve_alert(alert)
                
                # Clear potential resolve time
                if hasattr(alert, "_potential_resolve_time"):
                    delattr(alert, "_potential_resolve_time")
    
    def _check_repeat_notifications(self) -> None:
        """Check for alerts that need repeat notifications."""
        for alert_id, alert in list(self.alerts.items()):
            if alert.state != AlertState.FIRING:
                continue
            
            # Get rule
            rule = self.rules.get(alert.rule_id)
            if not rule or rule.repeat_interval <= 0:
                continue
            
            # Check if repeat interval reached
            if not alert.notified_at:
                continue
            
            duration = (datetime.now() - alert.notified_at).total_seconds()
            
            if duration >= rule.repeat_interval:
                # Send repeat notification
                self._notify_alert(alert, rule.notifications, is_repeat=True)
    
    def _resolve_alert(self, alert: Alert) -> None:
        """
        Resolve an alert.
        
        Args:
            alert: Alert to resolve
        """
        # Update alert state
        alert.state = AlertState.RESOLVED
        alert.resolved_at = datetime.now()
        alert.updated_at = datetime.now()
        
        # Move to history if enabled
        rule = self.rules.get(alert.rule_id)
        if rule:
            # Send resolution notification
            self._notify_alert(alert, rule.notifications)
            
            # Remove from active alerts
            if alert.id in self.alerts:
                # Add to history
                self.alert_history.append(alert)
                
                # Trim history if needed
                if len(self.alert_history) > self.max_history:
                    self.alert_history = self.alert_history[-self.max_history:]
                
                # Remove from active alerts
                del self.alerts[alert.id]
    
    def _notify_alert(
        self, 
        alert: Alert, 
        notification_types: List[NotificationType],
        is_repeat: bool = False,
    ) -> None:
        """
        Send notifications for an alert.
        
        Args:
            alert: Alert to notify about
            notification_types: Types of notifications to send
            is_repeat: Whether this is a repeat notification
        """
        # Check if alert is suppressed
        if alert.suppressed:
            if not alert.suppressed_until or datetime.now() < alert.suppressed_until:
                logger.debug(f"Alert {alert.id} is suppressed, skipping notification")
                return
            else:
                # Suppression expired
                alert.suppressed = False
                alert.suppressed_until = None
                alert.suppressed_reason = None
        
        # Get rule for this alert
        rule = self.rules.get(alert.rule_id)
        if not rule:
            logger.warning(f"Rule {alert.rule_id} not found for alert {alert.id}")
            return
        
        # Check for repeat suppression
        if is_repeat:
            # Repeat notification, nothing to suppress
            pass
        elif alert.notification_count > 0 and rule.suppress_repeat > 0:
            # Check if we should suppress based on time since last notification
            if alert.notified_at:
                time_since_last = (datetime.now() - alert.notified_at).total_seconds()
                
                if time_since_last < rule.suppress_repeat:
                    logger.debug(
                        f"Suppressing repeat notification for alert {alert.id} "
                        f"(last notified {time_since_last:.1f}s ago, suppress_repeat={rule.suppress_repeat}s)"
                    )
                    return
        
        # Send notification
        success = self.notifications.send_notification(alert, notification_types)
        
        if success:
            # Update notification timestamp and count
            alert.notified_at = datetime.now()
            alert.notification_count += 1
            logger.info(f"Sent {'repeat ' if is_repeat else ''}notification for alert {alert.id}")
    
    def _get_metric_values(self, metric_name: str) -> Dict[Union[str, Dict[str, str]], float]:
        """
        Get current values for a metric.
        
        Args:
            metric_name: Name of the metric
            
        Returns:
            Dictionary mapping label combinations to values
        """
        result = {}
        
        # Get all metrics
        metrics = self.monitoring.metrics.get_metrics()
        
        # Find the metric
        if metric_name in metrics:
            metric_data = metrics[metric_name]
            
            # Extract series data
            for series_key, series_data in metric_data.get("series", {}).items():
                # Get value and labels
                value = series_data.get("value")
                labels = series_data.get("labels", {})
                
                # Use labels as key if available, otherwise series key
                key = labels if labels else series_key
                
                # Add to result
                result[key] = value
        
        return result
    
    def _compare_value(self, value: float, threshold: float, comparison: str) -> bool:
        """
        Compare a value against a threshold.
        
        Args:
            value: Value to compare
            threshold: Threshold to compare against
            comparison: Comparison operator
            
        Returns:
            True if comparison is satisfied
        """
        if comparison == "gt":
            return value > threshold
        elif comparison == "lt":
            return value < threshold
        elif comparison == "eq":
            return value == threshold
        elif comparison == "ne":
            return value != threshold
        elif comparison == "ge":
            return value >= threshold
        elif comparison == "le":
            return value <= threshold
        else:
            raise ValueError(f"Invalid comparison: {comparison}")
    
    def _get_alert_group_key(self, rule: AlertRule, labels: Union[str, Dict[str, str]]) -> str:
        """
        Get a group key for an alert based on rule and labels.
        
        Args:
            rule: Alert rule
            labels: Series labels
            
        Returns:
            Group key string
        """
        # If labels is a string, use as-is
        if isinstance(labels, str):
            return labels
        
        # If no group_by, use hash of all labels
        if not rule.group_by:
            # Sort labels for consistent order
            sorted_items = sorted(labels.items())
            return "_".join(f"{k}:{v}" for k, v in sorted_items)
        
        # Otherwise, use only specified group_by labels
        parts = []
        for key in rule.group_by:
            if key in labels:
                parts.append(f"{key}:{labels[key]}")
        
        # If no matching group_by labels, use a hash of all labels
        if not parts:
            # Sort labels for consistent order
            sorted_items = sorted(labels.items())
            return "_".join(f"{k}:{v}" for k, v in sorted_items)
        
        return "_".join(parts)
    
    def _check_loop(self) -> None:
        """Background thread for periodic alert checking."""
        while self.running:
            try:
                # Check alerts
                self.check_alerts()
            except Exception as e:
                logger.error(f"Error in alert check loop: {e}")
            
            # Sleep until next check interval
            time.sleep(self.check_interval)


# Singleton instance
_instance = None

def get_instance(
    monitoring_manager: MonitoringManager,
    notification_manager: Optional[NotificationManager] = None,
) -> AlertManager:
    """
    Get or create the singleton alert manager instance.
    
    Args:
        monitoring_manager: MCP monitoring manager
        notification_manager: Optional notification manager
        
    Returns:
        AlertManager instance
    """
    global _instance
    if _instance is None:
        _instance = AlertManager(monitoring_manager, notification_manager)
    return _instance
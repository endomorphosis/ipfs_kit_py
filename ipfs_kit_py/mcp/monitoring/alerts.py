"""
Alerting System for MCP Server

This module provides an alerting and notification system:
- Configurable alert rules based on metrics
- Multiple notification channels (email, webhook, etc.)
- Alert aggregation and deduplication
- Alert history and tracking

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import os
import time
import logging
import json
import smtplib
import requests
import threading
import uuid
from enum import Enum
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Callable, Set

from ipfs_kit_py.mcp.monitoring import MetricsRegistry, MetricType, MetricUnit, MetricTag

# Configure logging
logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertState(Enum):
    """Alert states."""
    PENDING = "pending"  # Initial detection, not yet firing
    FIRING = "firing"    # Active alert
    RESOLVED = "resolved"  # Previously firing, now resolved
    ACKNOWLEDGED = "acknowledged"  # Acknowledged by a user


class NotificationChannel(Enum):
    """Notification channel types."""
    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"
    CONSOLE = "console"  # Log to console (for testing)


class AlertRule:
    """
    Alert rule definition.
    
    Defines conditions for triggering alerts based on metric values.
    """
    
    def __init__(
        self,
        name: str,
        metric_name: str,
        condition: str,
        threshold: float,
        duration: int = 0,
        severity: AlertSeverity = AlertSeverity.WARNING,
        description: str = "",
        labels: Dict[str, str] = None,
        annotations: Dict[str, str] = None,
        notification_channels: List[str] = None
    ):
        """
        Initialize an alert rule.
        
        Args:
            name: Alert rule name
            metric_name: Name of the metric to monitor
            condition: Comparison condition ('>', '>=', '<', '<=', '==', '!=')
            threshold: Threshold value for the condition
            duration: Duration in seconds the condition must be true before alerting (0 = immediate)
            severity: Alert severity level
            description: Human-readable description of the alert
            labels: Additional labels for the alert
            annotations: Additional annotations for context
            notification_channels: List of notification channel IDs to use for this alert
        """
        self.id = str(uuid.uuid4())
        self.name = name
        self.metric_name = metric_name
        self.condition = condition
        self.threshold = threshold
        self.duration = duration
        self.severity = severity
        self.description = description
        self.labels = labels or {}
        self.annotations = annotations or {}
        self.notification_channels = notification_channels or []
        
        # Validate condition
        if condition not in ['>', '>=', '<', '<=', '==', '!=']:
            raise ValueError(f"Invalid condition: {condition}. Must be one of '>', '>=', '<', '<=', '==', '!='")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the rule to a dictionary.
        
        Returns:
            Dictionary representation
        """
        return {
            "id": self.id,
            "name": self.name,
            "metric_name": self.metric_name,
            "condition": self.condition,
            "threshold": self.threshold,
            "duration": self.duration,
            "severity": self.severity.value,
            "description": self.description,
            "labels": self.labels,
            "annotations": self.annotations,
            "notification_channels": self.notification_channels
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AlertRule':
        """
        Create a rule from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            Alert rule instance
        """
        # Create instance
        instance = cls(
            name=data["name"],
            metric_name=data["metric_name"],
            condition=data["condition"],
            threshold=data["threshold"],
            duration=data.get("duration", 0),
            severity=AlertSeverity(data.get("severity", "warning")),
            description=data.get("description", ""),
            labels=data.get("labels", {}),
            annotations=data.get("annotations", {}),
            notification_channels=data.get("notification_channels", [])
        )
        
        # Set ID if provided
        if "id" in data:
            instance.id = data["id"]
        
        return instance
    
    def evaluate(self, value: float) -> bool:
        """
        Evaluate if the value meets the alert condition.
        
        Args:
            value: Metric value to evaluate
            
        Returns:
            True if the condition is met, False otherwise
        """
        if self.condition == '>':
            return value > self.threshold
        elif self.condition == '>=':
            return value >= self.threshold
        elif self.condition == '<':
            return value < self.threshold
        elif self.condition == '<=':
            return value <= self.threshold
        elif self.condition == '==':
            return value == self.threshold
        elif self.condition == '!=':
            return value != self.threshold
        else:
            # This should not happen due to validation in __init__
            return False


class Alert:
    """
    Alert instance.
    
    Represents an actual triggered alert based on a rule.
    """
    
    def __init__(
        self,
        rule: AlertRule,
        value: float,
        state: AlertState = AlertState.PENDING,
        triggered_at: Optional[datetime] = None,
        resolved_at: Optional[datetime] = None,
        acknowledged_at: Optional[datetime] = None,
        acknowledged_by: Optional[str] = None,
        metric_labels: Dict[str, str] = None
    ):
        """
        Initialize an alert.
        
        Args:
            rule: The rule that triggered this alert
            value: The value that triggered the alert
            state: Current alert state
            triggered_at: When the alert was first triggered
            resolved_at: When the alert was resolved (if applicable)
            acknowledged_at: When the alert was acknowledged (if applicable)
            acknowledged_by: Who acknowledged the alert (if applicable)
            metric_labels: Labels from the metric that triggered the alert
        """
        self.id = str(uuid.uuid4())
        self.rule = rule
        self.value = value
        self.state = state
        self.triggered_at = triggered_at or datetime.now()
        self.resolved_at = resolved_at
        self.acknowledged_at = acknowledged_at
        self.acknowledged_by = acknowledged_by
        self.metric_labels = metric_labels or {}
        self.last_notification_time = None
        self.notification_count = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the alert to a dictionary.
        
        Returns:
            Dictionary representation
        """
        return {
            "id": self.id,
            "rule": self.rule.to_dict(),
            "value": self.value,
            "state": self.state.value,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "acknowledged_by": self.acknowledged_by,
            "metric_labels": self.metric_labels,
            "notification_count": self.notification_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Alert':
        """
        Create an alert from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            Alert instance
        """
        # Create rule
        rule = AlertRule.from_dict(data["rule"])
        
        # Parse timestamps
        triggered_at = datetime.fromisoformat(data["triggered_at"]) if data.get("triggered_at") else None
        resolved_at = datetime.fromisoformat(data["resolved_at"]) if data.get("resolved_at") else None
        acknowledged_at = datetime.fromisoformat(data["acknowledged_at"]) if data.get("acknowledged_at") else None
        
        # Create instance
        instance = cls(
            rule=rule,
            value=data["value"],
            state=AlertState(data["state"]),
            triggered_at=triggered_at,
            resolved_at=resolved_at,
            acknowledged_at=acknowledged_at,
            acknowledged_by=data.get("acknowledged_by"),
            metric_labels=data.get("metric_labels", {})
        )
        
        # Set ID and notification info if provided
        if "id" in data:
            instance.id = data["id"]
        
        instance.notification_count = data.get("notification_count", 0)
        
        return instance
    
    def set_state(self, state: AlertState) -> None:
        """
        Update the alert state.
        
        Args:
            state: New state
        """
        if state == self.state:
            return
        
        self.state = state
        
        if state == AlertState.RESOLVED:
            self.resolved_at = datetime.now()
        elif state == AlertState.ACKNOWLEDGED:
            self.acknowledged_at = datetime.now()
    
    def acknowledge(self, user: str) -> None:
        """
        Acknowledge the alert.
        
        Args:
            user: User who acknowledged the alert
        """
        self.set_state(AlertState.ACKNOWLEDGED)
        self.acknowledged_by = user
    
    def get_summary(self) -> str:
        """
        Get a human-readable summary of the alert.
        
        Returns:
            Alert summary text
        """
        rule = self.rule
        condition_text = f"{rule.metric_name} {rule.condition} {rule.threshold}"
        
        if self.state == AlertState.PENDING:
            return f"PENDING: {rule.name} - {condition_text} (current: {self.value})"
        elif self.state == AlertState.FIRING:
            return f"FIRING: {rule.name} - {condition_text} (current: {self.value})"
        elif self.state == AlertState.RESOLVED:
            return f"RESOLVED: {rule.name} - {condition_text} (was: {self.value})"
        elif self.state == AlertState.ACKNOWLEDGED:
            return f"ACKNOWLEDGED: {rule.name} - {condition_text} (current: {self.value}) by {self.acknowledged_by}"
        else:
            return f"UNKNOWN STATE: {rule.name} - {condition_text} (current: {self.value})"
    
    def should_notify(self, min_interval: int = 300) -> bool:
        """
        Check if a notification should be sent for this alert.
        
        Args:
            min_interval: Minimum seconds between notifications
            
        Returns:
            True if notification should be sent
        """
        # Always notify on first alert or state change to FIRING
        if self.notification_count == 0 or (self.state == AlertState.FIRING and self.last_notification_time is None):
            return True
        
        # Don't notify if not in pending or firing state
        if self.state not in [AlertState.PENDING, AlertState.FIRING]:
            return False
        
        # Check if enough time has passed since last notification
        if self.last_notification_time is None:
            return True
        
        elapsed = (datetime.now() - self.last_notification_time).total_seconds()
        return elapsed >= min_interval


class NotificationConfig:
    """
    Configuration for a notification channel.
    """
    
    def __init__(
        self,
        id: str,
        name: str,
        type: NotificationChannel,
        config: Dict[str, Any]
    ):
        """
        Initialize notification channel configuration.
        
        Args:
            id: Channel identifier
            name: Human-readable name
            type: Channel type
            config: Type-specific configuration
        """
        self.id = id
        self.name = name
        self.type = type
        self.config = config
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary.
        
        Returns:
            Dictionary representation
        """
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "config": self.config
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NotificationConfig':
        """
        Create from dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            NotificationConfig instance
        """
        return cls(
            id=data["id"],
            name=data["name"],
            type=NotificationChannel(data["type"]),
            config=data["config"]
        )


class AlertManager:
    """
    Alert manager for MCP Server.
    
    Monitors metrics, evaluates alert rules, and sends notifications.
    """
    
    def __init__(
        self,
        metrics_registry: MetricsRegistry,
        config_path: str = None
    ):
        """
        Initialize the alert manager.
        
        Args:
            metrics_registry: MCP metrics registry
            config_path: Path to alert configuration file
        """
        self.metrics = metrics_registry
        self.config_path = config_path or os.path.join(
            os.path.expanduser("~"), ".ipfs_kit", "alert_config.json"
        )
        
        # Rules and channels
        self.rules: Dict[str, AlertRule] = {}
        self.notification_channels: Dict[str, NotificationConfig] = {}
        
        # Active and historical alerts
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.max_history = 1000
        
        # Metric value cache for duration-based alerts
        self.metric_triggers: Dict[str, Dict[str, datetime]] = {}
        
        # Lock for thread safety
        self.lock = threading.RLock()
        
        # Running state
        self.running = False
        self.check_thread = None
        self.check_interval = 30  # seconds
        
        # Load configuration if file exists
        self._load_config()
    
    def _load_config(self) -> None:
        """Load alert configuration from file."""
        if not os.path.exists(self.config_path):
            logger.info(f"Alert configuration file not found: {self.config_path}")
            self._init_default_config()
            return
        
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            # Load rules
            with self.lock:
                self.rules = {}
                for rule_data in config.get("rules", []):
                    rule = AlertRule.from_dict(rule_data)
                    self.rules[rule.id] = rule
            
            # Load notification channels
            with self.lock:
                self.notification_channels = {}
                for channel_data in config.get("notification_channels", []):
                    channel = NotificationConfig.from_dict(channel_data)
                    self.notification_channels[channel.id] = channel
            
            logger.info(f"Loaded {len(self.rules)} alert rules and {len(self.notification_channels)} notification channels")
        
        except Exception as e:
            logger.error(f"Error loading alert configuration: {e}")
            self._init_default_config()
    
    def _init_default_config(self) -> None:
        """Initialize default alert configuration."""
        with self.lock:
            # Default notification channel (console)
            console_channel = NotificationConfig(
                id="console",
                name="Console Logger",
                type=NotificationChannel.CONSOLE,
                config={}
            )
            self.notification_channels["console"] = console_channel
            
            # Default alert rules
            # High CPU usage
            cpu_rule = AlertRule(
                name="High CPU Usage",
                metric_name="system_cpu_usage",
                condition=">",
                threshold=90.0,
                duration=300,  # 5 minutes
                severity=AlertSeverity.WARNING,
                description="CPU usage is above 90% for 5 minutes",
                labels={"resource": "cpu"},
                notification_channels=["console"]
            )
            self.rules[cpu_rule.id] = cpu_rule
            
            # High memory usage
            memory_rule = AlertRule(
                name="High Memory Usage",
                metric_name="system_memory_usage",
                condition=">",
                threshold=90.0,
                duration=300,  # 5 minutes
                severity=AlertSeverity.WARNING,
                description="Memory usage is above 90% for 5 minutes",
                labels={"resource": "memory"},
                notification_channels=["console"]
            )
            self.rules[memory_rule.id] = memory_rule
            
            # Backend error rate
            error_rule = AlertRule(
                name="High Backend Error Rate",
                metric_name="backend_operations_total",
                condition=">",
                threshold=0.05,  # 5% error rate
                duration=300,  # 5 minutes
                severity=AlertSeverity.ERROR,
                description="Backend error rate is above 5% for 5 minutes",
                labels={"backend_type": "any"},
                notification_channels=["console"]
            )
            self.rules[error_rule.id] = error_rule
        
        # Save default config
        self._save_config()
    
    def _save_config(self) -> None:
        """Save alert configuration to file."""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            with self.lock:
                config = {
                    "rules": [rule.to_dict() for rule in self.rules.values()],
                    "notification_channels": [channel.to_dict() for channel in self.notification_channels.values()]
                }
            
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            logger.info(f"Saved alert configuration to {self.config_path}")
        
        except Exception as e:
            logger.error(f"Error saving alert configuration: {e}")
    
    def add_rule(self, rule: AlertRule) -> str:
        """
        Add an alert rule.
        
        Args:
            rule: Alert rule to add
            
        Returns:
            Rule ID
        """
        with self.lock:
            self.rules[rule.id] = rule
            self._save_config()
            return rule.id
    
    def update_rule(self, rule_id: str, rule: AlertRule) -> bool:
        """
        Update an alert rule.
        
        Args:
            rule_id: ID of rule to update
            rule: Updated rule
            
        Returns:
            True if successful
        """
        with self.lock:
            if rule_id not in self.rules:
                return False
            
            # Keep the same ID
            rule.id = rule_id
            self.rules[rule_id] = rule
            self._save_config()
            return True
    
    def delete_rule(self, rule_id: str) -> bool:
        """
        Delete an alert rule.
        
        Args:
            rule_id: ID of rule to delete
            
        Returns:
            True if successful
        """
        with self.lock:
            if rule_id not in self.rules:
                return False
            
            del self.rules[rule_id]
            self._save_config()
            return True
    
    def add_notification_channel(self, channel: NotificationConfig) -> str:
        """
        Add a notification channel.
        
        Args:
            channel: Notification channel to add
            
        Returns:
            Channel ID
        """
        with self.lock:
            self.notification_channels[channel.id] = channel
            self._save_config()
            return channel.id
    
    def update_notification_channel(self, channel_id: str, channel: NotificationConfig) -> bool:
        """
        Update a notification channel.
        
        Args:
            channel_id: ID of channel to update
            channel: Updated channel
            
        Returns:
            True if successful
        """
        with self.lock:
            if channel_id not in self.notification_channels:
                return False
            
            # Keep the same ID
            channel.id = channel_id
            self.notification_channels[channel_id] = channel
            self._save_config()
            return True
    
    def delete_notification_channel(self, channel_id: str) -> bool:
        """
        Delete a notification channel.
        
        Args:
            channel_id: ID of channel to delete
            
        Returns:
            True if successful
        """
        with self.lock:
            if channel_id not in self.notification_channels:
                return False
            
            del self.notification_channels[channel_id]
            self._save_config()
            return True
    
    def get_rule(self, rule_id: str) -> Optional[AlertRule]:
        """
        Get an alert rule by ID.
        
        Args:
            rule_id: Rule ID
            
        Returns:
            Alert rule or None if not found
        """
        with self.lock:
            return self.rules.get(rule_id)
    
    def get_notification_channel(self, channel_id: str) -> Optional[NotificationConfig]:
        """
        Get a notification channel by ID.
        
        Args:
            channel_id: Channel ID
            
        Returns:
            Notification channel or None if not found
        """
        with self.lock:
            return self.notification_channels.get(channel_id)
    
    def list_rules(self) -> List[AlertRule]:
        """
        List all alert rules.
        
        Returns:
            List of alert rules
        """
        with self.lock:
            return list(self.rules.values())
    
    def list_notification_channels(self) -> List[NotificationConfig]:
        """
        List all notification channels.
        
        Returns:
            List of notification channels
        """
        with self.lock:
            return list(self.notification_channels.values())
    
    def list_active_alerts(self) -> List[Alert]:
        """
        List active (firing or pending) alerts.
        
        Returns:
            List of active alerts
        """
        with self.lock:
            return list(self.active_alerts.values())
    
    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """
        Get alert history.
        
        Args:
            limit: Maximum number of alerts to return
            
        Returns:
            List of historical alerts
        """
        with self.lock:
            return self.alert_history[:limit]
    
    def acknowledge_alert(self, alert_id: str, user: str) -> bool:
        """
        Acknowledge an alert.
        
        Args:
            alert_id: Alert ID
            user: User acknowledging the alert
            
        Returns:
            True if successful
        """
        with self.lock:
            if alert_id not in self.active_alerts:
                return False
            
            alert = self.active_alerts[alert_id]
            alert.acknowledge(user)
            return True
    
    def start(self, interval: int = 30) -> None:
        """
        Start the alert manager.
        
        Args:
            interval: Check interval in seconds
        """
        if self.running:
            logger.warning("Alert manager already running")
            return
        
        self.check_interval = interval
        self.running = True
        
        # Start check thread
        self.check_thread = threading.Thread(
            target=self._check_loop,
            daemon=True
        )
        self.check_thread.start()
        
        logger.info(f"Started alert manager with interval {interval}s")
    
    def stop(self) -> None:
        """Stop the alert manager."""
        self.running = False
        
        if self.check_thread:
            self.check_thread.join(timeout=5.0)
            logger.info("Stopped alert manager")
    
    def _check_loop(self) -> None:
        """Background thread to check alert rules."""
        while self.running:
            try:
                self._check_rules()
            except Exception as e:
                logger.error(f"Error checking alert rules: {e}")
            
            # Sleep until next check
            time.sleep(self.check_interval)
    
    def _check_rules(self) -> None:
        """Check all alert rules against current metrics."""
        # Get all metrics
        all_metrics = self.metrics.get_metrics()
        
        # Check each rule
        with self.lock:
            for rule_id, rule in self.rules.items():
                self._evaluate_rule(rule, all_metrics)
        
        # Check for resolved alerts
        self._check_resolved_alerts(all_metrics)
    
    def _evaluate_rule(self, rule: AlertRule, metrics: Dict[str, Dict[str, Any]]) -> None:
        """
        Evaluate a single alert rule.
        
        Args:
            rule: Alert rule to evaluate
            metrics: Current metrics
        """
        metric_name = rule.metric_name
        
        # Skip if metric not found
        if metric_name not in metrics:
            return
        
        # Get metric data
        metric_data = metrics[metric_name]
        series_data = metric_data.get("series", {})
        
        # For each series of this metric
        for series_key, series in series_data.items():
            value = series.get("value")
            labels = series.get("labels", {})
            
            # Skip if no value
            if value is None:
                continue
            
            # Check if value meets condition
            if rule.evaluate(value):
                # If duration is zero, trigger immediately
                if rule.duration == 0:
                    self._trigger_alert(rule, value, labels)
                else:
                    # Check if this is a new trigger or continuing trigger
                    rule_series_key = f"{rule.id}:{series_key}"
                    trigger_key = (metric_name, rule_series_key)
                    
                    if trigger_key not in self.metric_triggers:
                        # New trigger, record start time
                        self.metric_triggers[trigger_key] = datetime.now()
                    else:
                        # Check if duration threshold reached
                        start_time = self.metric_triggers[trigger_key]
                        elapsed = (datetime.now() - start_time).total_seconds()
                        
                        if elapsed >= rule.duration:
                            # Duration threshold reached, trigger alert
                            self._trigger_alert(rule, value, labels)
            else:
                # Condition not met, reset trigger if any
                trigger_key = (metric_name, f"{rule.id}:{series_key}")
                if trigger_key in self.metric_triggers:
                    del self.metric_triggers[trigger_key]
    
    def _trigger_alert(self, rule: AlertRule, value: float, labels: Dict[str, str]) -> None:
        """
        Trigger an alert for a rule.
        
        Args:
            rule: Alert rule
            value: Current value
            labels: Metric labels
        """
        # Generate a deterministic alert ID for this rule + labels combination
        # This ensures we don't create duplicate alerts for the same condition
        alert_key = f"{rule.id}:{self._labels_to_key(labels)}"
        
        # Check if alert already exists
        if alert_key in self.active_alerts:
            # Update existing alert
            alert = self.active_alerts[alert_key]
            alert.value = value
            
            # If it was resolved, set back to firing
            if alert.state == AlertState.RESOLVED:
                alert.set_state(AlertState.FIRING)
                self._send_notifications(alert)
        else:
            # Create new alert
            alert = Alert(
                rule=rule,
                value=value,
                state=AlertState.FIRING,
                metric_labels=labels
            )
            
            # Add to active alerts
            self.active_alerts[alert_key] = alert
            
            # Send notifications
            self._send_notifications(alert)
    
    def _check_resolved_alerts(self, metrics: Dict[str, Dict[str, Any]]) -> None:
        """
        Check if any active alerts have been resolved.
        
        Args:
            metrics: Current metrics
        """
        resolved_keys = []
        
        # Check each active alert
        for alert_key, alert in self.active_alerts.items():
            # Skip acknowledged alerts
            if alert.state == AlertState.ACKNOWLEDGED:
                continue
            
            rule = alert.rule
            metric_name = rule.metric_name
            
            # Skip if metric not found
            if metric_name not in metrics:
                continue
            
            # Get metric data
            metric_data = metrics[metric_name]
            series_data = metric_data.get("series", {})
            
            # Try to find matching series
            series_key = self._find_matching_series(series_data, alert.metric_labels)
            
            if series_key is None:
                # Series not found, can't determine if resolved
                continue
            
            # Get current value
            value = series_data[series_key].get("value")
            
            if value is None:
                # No value, can't determine if resolved
                continue
            
            # Check if condition is no longer met
            if not rule.evaluate(value):
                # Alert resolved
                alert.set_state(AlertState.RESOLVED)
                alert.value = value
                
                # Send resolution notification
                self._send_notifications(alert)
                
                # Move to history
                self.alert_history.insert(0, alert)
                resolved_keys.append(alert_key)
                
                # Reset any duration triggers
                for trigger_key in list(self.metric_triggers.keys()):
                    if trigger_key[0] == metric_name and trigger_key[1].startswith(f"{rule.id}:"):
                        del self.metric_triggers[trigger_key]
        
        # Remove resolved alerts from active list
        for key in resolved_keys:
            del self.active_alerts[key]
        
        # Trim history if needed
        if len(self.alert_history) > self.max_history:
            self.alert_history = self.alert_history[:self.max_history]
    
    def _find_matching_series(self, series_data: Dict[str, Dict[str, Any]], 
                             labels: Dict[str, str]) -> Optional[str]:
        """
        Find a series key matching the given labels.
        
        Args:
            series_data: Series data dictionary
            labels: Labels to match
            
        Returns:
            Matching series key or None if not found
        """
        # Try to find exact match
        labels_key = self._labels_to_key(labels)
        
        for series_key, series in series_data.items():
            series_labels = series.get("labels", {})
            if self._labels_to_key(series_labels) == labels_key:
                return series_key
        
        # Try to find partial match (all alert labels match series labels)
        if labels:
            for series_key, series in series_data.items():
                series_labels = series.get("labels", {})
                match = True
                
                for k, v in labels.items():
                    if k not in series_labels or series_labels[k] != v:
                        match = False
                        break
                
                if match:
                    return series_key
        
        # No match found
        return None
    
    def _labels_to_key(self, labels: Dict[str, str]) -> str:
        """
        Convert labels dictionary to a string key.
        
        Args:
            labels: Labels dictionary
            
        Returns:
            String key
        """
        if not labels:
            return "_no_labels_"
        
        return "_".join(f"{k}:{v}" for k, v in sorted(labels.items()))
    
    def _send_notifications(self, alert: Alert) -> None:
        """
        Send notifications for an alert.
        
        Args:
            alert: Alert to send notifications for
        """
        # Check if notification should be sent
        if not alert.should_notify():
            return
        
        # Get notification channels for this alert
        channel_ids = alert.rule.notification_channels
        
        # Send to each channel
        for channel_id in channel_ids:
            if channel_id not in self.notification_channels:
                logger.warning(f"Notification channel {channel_id} not found")
                continue
            
            channel = self.notification_channels[channel_id]
            
            try:
                self._send_to_channel(alert, channel)
            except Exception as e:
                logger.error(f"Error sending notification to channel {channel_id}: {e}")
        
        # Update notification info
        alert.last_notification_time = datetime.now()
        alert.notification_count += 1
    
    def _send_to_channel(self, alert: Alert, channel: NotificationConfig) -> None:
        """
        Send an alert to a notification channel.
        
        Args:
            alert: Alert to send
            channel: Notification channel
        """
        if channel.type == NotificationChannel.CONSOLE:
            # Log to console
            level = logging.INFO
            if alert.rule.severity == AlertSeverity.WARNING:
                level = logging.WARNING
            elif alert.rule.severity == AlertSeverity.ERROR:
                level = logging.ERROR
            elif alert.rule.severity == AlertSeverity.CRITICAL:
                level = logging.CRITICAL
            
            logger.log(level, f"Alert: {alert.get_summary()}")
        
        elif channel.type == NotificationChannel.EMAIL:
            # Send email
            self._send_email(alert, channel.config)
        
        elif channel.type == NotificationChannel.WEBHOOK:
            # Send webhook
            self._send_webhook(alert, channel.config)
        
        elif channel.type == NotificationChannel.SLACK:
            # Send Slack message
            self._send_slack(alert, channel.config)
    
    def _send_email(self, alert: Alert, config: Dict[str, Any]) -> None:
        """
        Send an alert via email.
        
        Args:
            alert: Alert to send
            config: Email configuration
        """
        # Get configuration
        smtp_host = config.get("smtp_host", "localhost")
        smtp_port = config.get("smtp_port", 25)
        smtp_user = config.get("smtp_user")
        smtp_password = config.get("smtp_password")
        from_addr = config.get("from", "mcp-alerts@localhost")
        to_addrs = config.get("to", [])
        
        if not to_addrs:
            logger.warning("No recipients configured for email notifications")
            return
        
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"MCP Alert: {alert.rule.name} - {alert.state.value.upper()}"
        msg["From"] = from_addr
        msg["To"] = ", ".join(to_addrs)
        
        # Create plain text content
        text_content = f"""
Alert: {alert.rule.name}
Status: {alert.state.value.upper()}
Severity: {alert.rule.severity.value}
Time: {alert.triggered_at.isoformat()}
Metric: {alert.rule.metric_name} {alert.rule.condition} {alert.rule.threshold} (current: {alert.value})
Labels: {alert.metric_labels}
        
{alert.rule.description}
        """
        
        # Create HTML content
        color = "#000000"
        if alert.rule.severity == AlertSeverity.WARNING:
            color = "#FFA500"  # Orange
        elif alert.rule.severity == AlertSeverity.ERROR:
            color = "#FF0000"  # Red
        elif alert.rule.severity == AlertSeverity.CRITICAL:
            color = "#800000"  # Dark red
        
        html_content = f"""
<html>
<body>
    <h2 style="color: {color};">MCP Alert: {alert.rule.name}</h2>
    <p><strong>Status:</strong> {alert.state.value.upper()}</p>
    <p><strong>Severity:</strong> {alert.rule.severity.value}</p>
    <p><strong>Time:</strong> {alert.triggered_at.isoformat()}</p>
    <p><strong>Metric:</strong> {alert.rule.metric_name} {alert.rule.condition} {alert.rule.threshold} (current: {alert.value})</p>
    <p><strong>Labels:</strong> {alert.metric_labels}</p>
    <p><strong>Description:</strong> {alert.rule.description}</p>
</body>
</html>
        """
        
        # Attach content
        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))
        
        # Send email
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            
            server.send_message(msg)
    
    def _send_webhook(self, alert: Alert, config: Dict[str, Any]) -> None:
        """
        Send an alert via webhook.
        
        Args:
            alert: Alert to send
            config: Webhook configuration
        """
        # Get configuration
        url = config.get("url")
        headers = config.get("headers", {})
        include_details = config.get("include_details", True)
        
        if not url:
            logger.warning("No URL configured for webhook notifications")
            return
        
        # Create payload
        payload = {
            "alert": {
                "name": alert.rule.name,
                "state": alert.state.value,
                "severity": alert.rule.severity.value,
                "time": alert.triggered_at.isoformat(),
                "summary": alert.get_summary()
            }
        }
        
        # Add details if requested
        if include_details:
            payload["alert"]["details"] = {
                "metric": alert.rule.metric_name,
                "condition": alert.rule.condition,
                "threshold": alert.rule.threshold,
                "value": alert.value,
                "labels": alert.metric_labels,
                "description": alert.rule.description
            }
        
        # Send webhook
        response = requests.post(
            url,
            json=payload,
            headers=headers
        )
        
        # Check response
        if not response.ok:
            logger.warning(f"Webhook notification failed: {response.status_code} {response.text}")
    
    def _send_slack(self, alert: Alert, config: Dict[str, Any]) -> None:
        """
        Send an alert via Slack.
        
        Args:
            alert: Alert to send
            config: Slack configuration
        """
        # Get configuration
        webhook_url = config.get("webhook_url")
        channel = config.get("channel")
        username = config.get("username", "MCP Alerts")
        
        if not webhook_url:
            logger.warning("No webhook URL configured for Slack notifications")
            return
        
        # Set color based on severity
        color = "#000000"
        if alert.rule.severity == AlertSeverity.WARNING:
            color = "#FFA500"  # Orange
        elif alert.rule.severity == AlertSeverity.ERROR:
            color = "#FF0000"  # Red
        elif alert.rule.severity == AlertSeverity.CRITICAL:
            color = "#800000"  # Dark red
        
        # Create payload
        payload = {
            "username": username,
            "icon_emoji": ":warning:",
            "attachments": [
                {
                    "fallback": alert.get_summary(),
                    "color": color,
                    "title": f"MCP Alert: {alert.rule.name}",
                    "text": alert.get_summary(),
                    "fields": [
                        {
                            "title": "State",
                            "value": alert.state.value.upper(),
                            "short": True
                        },
                        {
                            "title": "Severity",
                            "value": alert.rule.severity.value,
                            "short": True
                        },
                        {
                            "title": "Metric",
                            "value": f"{alert.rule.metric_name} {alert.rule.condition} {alert.rule.threshold}",
                            "short": True
                        },
                        {
                            "title": "Value",
                            "value": str(alert.value),
                            "short": True
                        }
                    ],
                    "ts": int(alert.triggered_at.timestamp())
                }
            ]
        }
        
        # Add channel if specified
        if channel:
            payload["channel"] = channel
        
        # Send to Slack
        response = requests.post(
            webhook_url,
            json=payload
        )
        
        # Check response
        if not response.ok:
            logger.warning(f"Slack notification failed: {response.status_code} {response.text}")


def setup_alert_manager(app, metrics_registry: MetricsRegistry, backend_registry: Optional[Dict[str, Any]] = None) -> AlertManager:
    """
    Set up alert manager for MCP server.
    
    Args:
        app: FastAPI application
        metrics_registry: MCP metrics registry
        backend_registry: Optional dictionary mapping backend names to instances
        
    Returns:
        Alert manager
    """
    # Create alert manager
    alert_manager = AlertManager(metrics_registry)
    
    # Add API endpoints
    @app.get("/api/v0/monitoring/alerts")
    async def get_alerts():
        """Get active alerts."""
        return {
            "active": [alert.to_dict() for alert in alert_manager.list_active_alerts()],
            "history": [alert.to_dict() for alert in alert_manager.get_alert_history()]
        }
    
    @app.get("/api/v0/monitoring/rules")
    async def get_rules():
        """Get alert rules."""
        return {
            "rules": [rule.to_dict() for rule in alert_manager.list_rules()]
        }
    
    @app.get("/api/v0/monitoring/channels")
    async def get_notification_channels():
        """Get notification channels."""
        return {
            "channels": [channel.to_dict() for channel in alert_manager.list_notification_channels()]
        }
    
    @app.post("/api/v0/monitoring/alerts/{alert_id}/acknowledge")
    async def acknowledge_alert(alert_id: str, user: str = "anonymous"):
        """Acknowledge an alert."""
        success = alert_manager.acknowledge_alert(alert_id, user)
        if not success:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
        
        return {"status": "acknowledged", "alert_id": alert_id, "user": user}
    
    # Start alert manager
    alert_manager.start()
    
    logger.info("Alert manager set up")
    return alert_manager
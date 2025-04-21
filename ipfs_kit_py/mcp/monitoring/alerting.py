"""
Alerting system for the MCP server.

This module provides alerting capabilities for monitoring MCP services.
"""

import asyncio
import json
import logging
import os
import smtplib
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

import aiofiles
import aiohttp
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)


class AlertRule(BaseModel):
    """Alert rule definition."""

    id: str = Field(..., description="Unique identifier for the rule")
    name: str = Field(..., description="Name of the rule")
    description: Optional[str] = Field(None, description="Description of the rule")
    query: str = Field(..., description="PromQL query for the alert condition")
    threshold: float = Field(..., description="Threshold value for triggering the alert")
    comparison: str = Field(..., description="Comparison operator: gt, lt, eq, ne, ge, le")
    duration: int = Field(
        0, description="Duration in seconds the condition must be true before alerting"
    )
    severity: str = Field("warning", description="Severity level: critical, warning, info")
    labels: Dict[str, str] = Field(default_factory=dict, description="Labels for the alert")
    annotations: Dict[str, str] = Field(
        default_factory=dict, description="Annotations for the alert"
    )
    enabled: bool = Field(True, description="Whether the rule is enabled")
    silenced_until: Optional[float] = Field(
        None, description="Timestamp until which the alert is silenced"
    )
    notify_channels: List[str] = Field(
        default_factory=list, description="Notification channels to use"
    )

    @validator("comparison")
    def comparison_must_be_valid(cls, v):
        valid_operators = {"gt", "lt", "eq", "ne", "ge", "le"}
        if v not in valid_operators:
            raise ValueError(f"Invalid comparison operator. Must be one of: {valid_operators}")
        return v

    @validator("severity")
    def severity_must_be_valid(cls, v):
        valid_severities = {"critical", "warning", "info"}
        if v not in valid_severities:
            raise ValueError(f"Invalid severity. Must be one of: {valid_severities}")
        return v


class AlertInstance(BaseModel):
    """Alert instance definition."""

    id: str = Field(..., description="Unique identifier for the alert instance")
    rule_id: str = Field(..., description="ID of the rule that triggered this alert")
    name: str = Field(..., description="Name of the alert")
    description: Optional[str] = Field(None, description="Description of the alert")
    query: str = Field(..., description="Query that triggered the alert")
    value: float = Field(..., description="Value that triggered the alert")
    threshold: float = Field(..., description="Threshold value")
    comparison: str = Field(..., description="Comparison operator used")
    severity: str = Field(..., description="Severity level")
    labels: Dict[str, str] = Field(default_factory=dict, description="Labels for the alert")
    annotations: Dict[str, str] = Field(
        default_factory=dict, description="Annotations for the alert"
    )
    start_time: float = Field(..., description="Timestamp when the alert started")
    end_time: Optional[float] = Field(None, description="Timestamp when the alert ended")
    status: str = Field("firing", description="Status: firing, resolved, silenced")
    notified: bool = Field(False, description="Whether notifications have been sent")
    last_notification: Optional[float] = Field(None, description="Timestamp of last notification")
    repeat_notification: bool = Field(False, description="Whether to repeat notifications")
    repeat_interval: int = Field(
        3600, description="Interval in seconds for repeating notifications"
    )


class NotificationChannel(BaseModel):
    """Notification channel definition."""

    id: str = Field(..., description="Unique identifier for the notification channel")
    name: str = Field(..., description="Name of the channel")
    type: str = Field(..., description="Type: email, slack, webhook, console")
    config: Dict[str, Any] = Field(..., description="Configuration for the channel")
    enabled: bool = Field(True, description="Whether the channel is enabled")
    send_resolved: bool = Field(True, description="Whether to send resolved notifications")
    filter_severity: List[str] = Field(
        default_factory=lambda: ["critical", "warning", "info"],
        description="Severities to include",
    )
    filter_labels: Dict[str, str] = Field(
        default_factory=dict, description="Labels that must match for notifications"
    )


class AlertingService:
    """
    Service for managing alerts and notifications.

    This service monitors metrics, triggers alerts, and sends notifications
    based on defined rules and channels.
    """

    def __init__(self, prometheus_url: str = "http://localhost:9090/api/v1"):
        """
        Initialize the alerting service.

        Args:
            prometheus_url: URL of the Prometheus API
        """
        self.prometheus_url = prometheus_url

        # Rules and alert state
        self.rules: Dict[str, AlertRule] = {}
        self.alerts: Dict[str, AlertInstance] = {}
        self.channels: Dict[str, NotificationChannel] = {}

        # In-memory state of previous evaluations
        self.evaluation_state: Dict[str, Dict[str, Any]] = {}

        # Tasks
        self.evaluation_task = None
        self.notification_task = None
        self.rule_load_task = None
        self.channel_load_task = None

        # Configuration and state data paths
        self.rules_file = "/tmp/ipfs_kit/mcp/alerting/rules.json"
        self.channels_file = "/tmp/ipfs_kit/mcp/alerting/channels.json"
        self.alerts_file = "/tmp/ipfs_kit/mcp/alerting/alerts.json"

    async def start(self):
        """Start the alerting service."""
        logger.info("Starting alerting service")

        # Create data directories

        os.makedirs(os.path.dirname(self.rules_file), exist_ok=True)

        # Load rules and channels
        await self.load_rules()
        await self.load_channels()
        await self.load_alerts()

        # Start background tasks
        self.evaluation_task = asyncio.create_task(self._evaluate_rules_loop())
        self.notification_task = asyncio.create_task(self._process_notifications_loop())

        logger.info("Alerting service started")

    async def stop(self):
        """Stop the alerting service."""
        logger.info("Stopping alerting service")

        # Cancel background tasks
        if self.evaluation_task:
            self.evaluation_task.cancel()
            try:
                await self.evaluation_task
            except asyncio.CancelledError:
                pass

        if self.notification_task:
            self.notification_task.cancel()
            try:
                await self.notification_task
            except asyncio.CancelledError:
                pass

        # Save current state
        await self.save_alerts()

        logger.info("Alerting service stopped")

    async def load_rules(self):
        """Load alert rules from storage."""
        try:
            if os.path.exists(self.rules_file):
                async with aiofiles.open(self.rules_file, "r") as f:
                    content = await f.read()
                    rules_data = json.loads(content)

                    for rule_data in rules_data:
                        rule = AlertRule(**rule_data)
                        self.rules[rule.id] = rule

                    logger.info(f"Loaded {len(self.rules)} alert rules")
            else:
                logger.info("No alert rules file found, starting with empty rules")
        except Exception as e:
            logger.error(f"Error loading alert rules: {e}")

    async def save_rules(self):
        """Save alert rules to storage."""
        try:
            rules_data = [rule.dict() for rule in self.rules.values()]

            async with aiofiles.open(self.rules_file, "w") as f:
                await f.write(json.dumps(rules_data, indent=2))

            logger.info(f"Saved {len(rules_data)} alert rules")
        except Exception as e:
            logger.error(f"Error saving alert rules: {e}")

    async def load_channels(self):
        """Load notification channels from storage."""
        try:
            if os.path.exists(self.channels_file):
                async with aiofiles.open(self.channels_file, "r") as f:
                    content = await f.read()
                    channels_data = json.loads(content)

                    for channel_data in channels_data:
                        channel = NotificationChannel(**channel_data)
                        self.channels[channel.id] = channel

                    logger.info(f"Loaded {len(self.channels)} notification channels")
            else:
                # Create default console channel
                console_channel = NotificationChannel(
                    id="default_console",
                    name="Console",
                    type="console",
                    config={},
                    enabled=True,
                )
                self.channels[console_channel.id] = console_channel

                await self.save_channels()
                logger.info("Created default notification channel")
        except Exception as e:
            logger.error(f"Error loading notification channels: {e}")

    async def save_channels(self):
        """Save notification channels to storage."""
        try:
            channels_data = [channel.dict() for channel in self.channels.values()]

            async with aiofiles.open(self.channels_file, "w") as f:
                await f.write(json.dumps(channels_data, indent=2))

            logger.info(f"Saved {len(channels_data)} notification channels")
        except Exception as e:
            logger.error(f"Error saving notification channels: {e}")

    async def load_alerts(self):
        """Load active alerts from storage."""
        try:
            if os.path.exists(self.alerts_file):
                async with aiofiles.open(self.alerts_file, "r") as f:
                    content = await f.read()
                    alerts_data = json.loads(content)

                    for alert_data in alerts_data:
                        alert = AlertInstance(**alert_data)
                        # Only load still-firing alerts
                        if alert.status == "firing":
                            self.alerts[alert.id] = alert

                    logger.info(f"Loaded {len(self.alerts)} active alerts")
        except Exception as e:
            logger.error(f"Error loading alerts: {e}")

    async def save_alerts(self):
        """Save active alerts to storage."""
        try:
            alerts_data = [alert.dict() for alert in self.alerts.values()]

            async with aiofiles.open(self.alerts_file, "w") as f:
                await f.write(json.dumps(alerts_data, indent=2))

            logger.info(f"Saved {len(alerts_data)} alerts")
        except Exception as e:
            logger.error(f"Error saving alerts: {e}")

    async def _evaluate_rules_loop(self):
        """Continuously evaluate alert rules."""
        while True:
            try:
                await self._evaluate_rules()
            except Exception as e:
                logger.error(f"Error evaluating alert rules: {e}")

            # Sleep for 30 seconds before next evaluation
            await asyncio.sleep(30)

    async def _evaluate_rules(self):
        """Evaluate all enabled alert rules."""
        for rule_id, rule in self.rules.items():
            if not rule.enabled:
                continue

            # Skip silenced rules
            if rule.silenced_until and rule.silenced_until > time.time():
                continue

            try:
                # Query Prometheus
                value = await self._query_prometheus(rule.query)

                # Check if rule condition is met
                is_triggered = self._check_condition(value, rule.comparison, rule.threshold)

                # Update evaluation state for this rule
                if rule_id not in self.evaluation_state:
                    self.evaluation_state[rule_id] = {
                        "triggered": False,
                        "first_triggered": 0,
                        "value": value,
                    }

                # Update state based on current evaluation
                if is_triggered:
                    # Rule is currently triggered
                    state = self.evaluation_state[rule_id]

                    if not state["triggered"]:
                        # First time triggered
                        state["triggered"] = True
                        state["first_triggered"] = time.time()
                        state["value"] = value

                    # Check if condition has been true for the required duration
                    duration_met = (time.time() - state["first_triggered"]) >= rule.duration

                    if duration_met:
                        # Create or update alert
                        await self._create_or_update_alert(rule, value)
                else:
                    # Rule is not triggered
                    state = self.evaluation_state[rule_id]

                    if state["triggered"]:
                        # Was previously triggered, now resolved
                        state["triggered"] = False
                        state["first_triggered"] = 0

                        # Resolve any alerts for this rule
                        await self._resolve_alerts(rule_id)
            except Exception as e:
                logger.error(f"Error evaluating rule {rule_id}: {e}")

    async def _query_prometheus(self, query: str) -> float:
        """
        Query Prometheus and return the result value.

        Args:
            query: PromQL query

        Returns:
            Result value
        """
        url = f"{self.prometheus_url}/query"
        params = {"query": query}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Prometheus query error: {error_text}")
                        return 0

                    data = await response.json()

                    if data["status"] != "success":
                        logger.error(
                            f"Prometheus query failed: {data.get('error', 'Unknown error')}"
                        )
                        return 0

                    # Process result based on result type
                    result_type = data["data"]["resultType"]

                    if result_type == "vector" and len(data["data"]["result"]) > 0:
                        # Return the value of the first result
                        return float(data["data"]["result"][0]["value"][1])
                    elif result_type == "scalar":
                        return float(data["data"]["result"][1])
                    else:
                        logger.warning(f"Unsupported result type or empty result: {result_type}")
                        return 0
        except Exception as e:
            logger.error(f"Error querying Prometheus: {e}")
            return 0

    def _check_condition(self, value: float, comparison: str, threshold: float) -> bool:
        """
        Check if a condition is met.

        Args:
            value: Value to check
            comparison: Comparison operator
            threshold: Threshold value

        Returns:
            True if condition is met
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
            logger.error(f"Invalid comparison operator: {comparison}")
            return False

    async def _create_or_update_alert(self, rule: AlertRule, value: float):
        """
        Create a new alert or update an existing one.

        Args:
            rule: Alert rule
            value: Current value
        """
        # Check if an alert already exists for this rule
        existing_alert = None
        for alert in self.alerts.values():
            if alert.rule_id == rule.id and alert.status == "firing":
                existing_alert = alert
                break

        if existing_alert:
            # Update existing alert
            existing_alert.value = value
            existing_alert.last_notification = (
                None if existing_alert.repeat_notification else existing_alert.last_notification
            )
        else:
            # Create new alert
            import uuid

            alert_id = f"alert_{uuid.uuid4().hex}"

            # Build alert from rule
            alert = AlertInstance(
                id=alert_id,
                rule_id=rule.id,
                name=rule.name,
                description=rule.description,
                query=rule.query,
                value=value,
                threshold=rule.threshold,
                comparison=rule.comparison,
                severity=rule.severity,
                labels=rule.labels,
                annotations=rule.annotations,
                start_time=time.time(),
                status="firing",
                notified=False,
                repeat_notification=True,
                repeat_interval=3600,  # 1 hour default
            )

            self.alerts[alert_id] = alert
            logger.info(f"Created new alert: {alert.name} [{alert.severity}]")

    async def _resolve_alerts(self, rule_id: str):
        """
        Resolve all alerts for a rule.

        Args:
            rule_id: Rule ID
        """
        for alert_id, alert in list(self.alerts.items()):
            if alert.rule_id == rule_id and alert.status == "firing":
                alert.status = "resolved"
                alert.end_time = time.time()

                # Keep resolved alerts for some time
                logger.info(f"Resolved alert: {alert.name}")

                # Send resolution notifications
                await self._send_resolution_notifications(alert)

    async def _process_notifications_loop(self):
        """Continuously process notifications for alerts."""
        while True:
            try:
                # Process notifications for all firing alerts
                for alert_id, alert in list(self.alerts.items()):
                    if alert.status == "firing":
                        # Check if notification should be sent
                        if not alert.notified:
                            # Initial notification
                            await self._send_alert_notifications(alert)
                            alert.notified = True
                            alert.last_notification = time.time()
                        elif alert.repeat_notification:
                            # Check if repeat interval has passed
                            time_since_last = time.time() - (alert.last_notification or 0)
                            if time_since_last >= alert.repeat_interval:
                                await self._send_alert_notifications(alert)
                                alert.last_notification = time.time()

                # Clean up old resolved alerts
                current_time = time.time()
                for alert_id, alert in list(self.alerts.items()):
                    if alert.status == "resolved" and alert.end_time:
                        # Remove alerts resolved more than 24 hours ago
                        if current_time - alert.end_time > 86400:
                            del self.alerts[alert_id]
            except Exception as e:
                logger.error(f"Error processing notifications: {e}")

            # Save current alert state
            await self.save_alerts()

            # Sleep for 10 seconds before next iteration
            await asyncio.sleep(10)

    async def _send_alert_notifications(self, alert: AlertInstance):
        """
        Send notifications for an alert.

        Args:
            alert: Alert instance
        """
        # Get rule
        rule = self.rules.get(alert.rule_id)
        if not rule:
            logger.warning(f"Cannot find rule {alert.rule_id} for alert {alert.id}")
            return

        # Get channels to notify
        channels_to_notify = []
        if rule.notify_channels:
            # Use channels specified in the rule
            for channel_id in rule.notify_channels:
                channel = self.channels.get(channel_id)
                if channel and channel.enabled:
                    # Check severity filter
                    if alert.severity in channel.filter_severity:
                        # Check label filter
                        labels_match = True
                        for k, v in channel.filter_labels.items():
                            if alert.labels.get(k) != v:
                                labels_match = False
                                break

                        if labels_match:
                            channels_to_notify.append(channel)
        else:
            # Use all enabled channels
            for channel in self.channels.values():
                if channel.enabled and alert.severity in channel.filter_severity:
                    channels_to_notify.append(channel)

        # Send notifications
        for channel in channels_to_notify:
            try:
                await self._send_notification(channel, alert)
                logger.info(f"Sent {alert.severity} alert '{alert.name}' to {channel.name}")
            except Exception as e:
                logger.error(f"Error sending notification to {channel.name}: {e}")

    async def _send_resolution_notifications(self, alert: AlertInstance):
        """
        Send resolution notifications for an alert.

        Args:
            alert: Alert instance
        """
        # Get rule
        rule = self.rules.get(alert.rule_id)
        if not rule:
            logger.warning(f"Cannot find rule {alert.rule_id} for alert {alert.id}")
            return

        # Get channels to notify
        channels_to_notify = []
        if rule.notify_channels:
            # Use channels specified in the rule
            for channel_id in rule.notify_channels:
                channel = self.channels.get(channel_id)
                if channel and channel.enabled and channel.send_resolved:
                    if alert.severity in channel.filter_severity:
                        channels_to_notify.append(channel)
        else:
            # Use all enabled channels
            for channel in self.channels.values():
                if (
                    channel.enabled
                    and channel.send_resolved
                    and alert.severity in channel.filter_severity
                ):
                    channels_to_notify.append(channel)

        # Send notifications
        for channel in channels_to_notify:
            try:
                await self._send_resolution_notification(channel, alert)
                logger.info(f"Sent resolution for alert '{alert.name}' to {channel.name}")
            except Exception as e:
                logger.error(f"Error sending resolution notification to {channel.name}: {e}")

    async def _send_notification(self, channel: NotificationChannel, alert: AlertInstance):
        """
        Send a notification using a specific channel.

        Args:
            channel: Notification channel
            alert: Alert instance
        """
        if channel.type == "email":
            await self._send_email_notification(channel, alert)
        elif channel.type == "slack":
            await self._send_slack_notification(channel, alert)
        elif channel.type == "webhook":
            await self._send_webhook_notification(channel, alert)
        elif channel.type == "console":
            self._send_console_notification(alert)
        else:
            logger.warning(f"Unsupported notification channel type: {channel.type}")

    async def _send_resolution_notification(
        self, channel: NotificationChannel, alert: AlertInstance
    ):
        """
        Send a resolution notification using a specific channel.

        Args:
            channel: Notification channel
            alert: Alert instance
        """
        if channel.type == "email":
            await self._send_email_resolution(channel, alert)
        elif channel.type == "slack":
            await self._send_slack_resolution(channel, alert)
        elif channel.type == "webhook":
            await self._send_webhook_resolution(channel, alert)
        elif channel.type == "console":
            self._send_console_resolution(alert)
        else:
            logger.warning(f"Unsupported notification channel type: {channel.type}")

    async def _send_email_notification(self, channel: NotificationChannel, alert: AlertInstance):
        """
        Send an email notification.

        Args:
            channel: Email channel
            alert: Alert instance
        """
        config = channel.config
        if not all(
            k in config for k in ["smtp_server", "smtp_port", "from_address", "to_addresses"]
        ):
            logger.error(f"Missing required email configuration for channel {channel.name}")
            return

        # Create email
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[{alert.severity.upper()}] {alert.name}"
        msg["From"] = config["from_address"]
        msg["To"] = ", ".join(config["to_addresses"])

        # Create text content
        text_content = f"""
Alert: {alert.name}
Severity: {alert.severity}
Status: {alert.status}
Time: {datetime.fromtimestamp(alert.start_time).strftime("%Y-%m-%d %H:%M:%S")}
Value: {alert.value} {alert.comparison} {alert.threshold}

{alert.description or ""}

Labels:
{json.dumps(alert.labels, indent=2)}

Annotations:
{json.dumps(alert.annotations, indent=2)}
"""
        # Create HTML content
        html_content = f"""
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; }}
        .alert {{ padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        .alert-critical {{ background-color: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; }}
        .alert-warning {{ background-color: #fff3cd; border: 1px solid #ffeeba; color: #856404; }}
        .alert-info {{ background-color: #d1ecf1; border: 1px solid #bee5eb; color: #0c5460; }}
        .label {{ font-weight: bold; }}
    </style>
</head>
<body>
    <div class="alert alert-{alert.severity}">
        <h2>Alert: {alert.name}</h2>
        <p><span class="label">Severity:</span> {alert.severity}</p>
        <p><span class="label">Status:</span> {alert.status}</p>
        <p><span class="label">Time:</span> {datetime.fromtimestamp(alert.start_time).strftime("%Y-%m-%d %H:%M:%S")}</p>
        <p><span class="label">Value:</span> {alert.value} {alert.comparison} {alert.threshold}</p>
        
        {f"<p>{alert.description}</p>" if alert.description else ""}
        
        <h3>Labels:</h3>
        <pre>{json.dumps(alert.labels, indent=2)}</pre>
        
        <h3>Annotations:</h3>
        <pre>{json.dumps(alert.annotations, indent=2)}</pre>
    </div>
</body>
</html>
"""
        # Attach parts
        part1 = MIMEText(text_content, "plain")
        part2 = MIMEText(html_content, "html")
        msg.attach(part1)
        msg.attach(part2)

        # Send email
        use_ssl = config.get("use_ssl", False)
        smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP

        with smtp_class(config["smtp_server"], config["smtp_port"]) as server:
            if not use_ssl and config.get("use_tls", False):
                server.starttls()

            if "username" in config and "password" in config:
                server.login(config["username"], config["password"])

            server.send_message(msg)

    async def _send_email_resolution(self, channel: NotificationChannel, alert: AlertInstance):
        """
        Send an email resolution notification.

        Args:
            channel: Email channel
            alert: Alert instance
        """
        config = channel.config
        if not all(
            k in config for k in ["smtp_server", "smtp_port", "from_address", "to_addresses"]
        ):
            logger.error(f"Missing required email configuration for channel {channel.name}")
            return

        # Create email
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[RESOLVED] {alert.name}"
        msg["From"] = config["from_address"]
        msg["To"] = ", ".join(config["to_addresses"])

        # Create text content
        text_content = f"""
Alert Resolved: {alert.name}
Severity: {alert.severity}
Status: {alert.status}
Started: {datetime.fromtimestamp(alert.start_time).strftime("%Y-%m-%d %H:%M:%S")}
Resolved: {datetime.fromtimestamp(alert.end_time).strftime("%Y-%m-%d %H:%M:%S") if alert.end_time else "Unknown"}
Duration: {self._format_duration(alert.end_time - alert.start_time) if alert.end_time else "Unknown"}

{alert.description or ""}

Labels:
{json.dumps(alert.labels, indent=2)}

Annotations:
{json.dumps(alert.annotations, indent=2)}
"""
        # Create HTML content
        html_content = f"""
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; }}
        .alert {{ padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        .alert-resolved {{ background-color: #d4edda; border: 1px solid #c3e6cb; color: #155724; }}
        .label {{ font-weight: bold; }}
    </style>
</head>
<body>
    <div class="alert alert-resolved">
        <h2>Alert Resolved: {alert.name}</h2>
        <p><span class="label">Severity:</span> {alert.severity}</p>
        <p><span class="label">Status:</span> {alert.status}</p>
        <p><span class="label">Started:</span> {datetime.fromtimestamp(alert.start_time).strftime("%Y-%m-%d %H:%M:%S")}</p>
        <p><span class="label">Resolved:</span> {datetime.fromtimestamp(alert.end_time).strftime("%Y-%m-%d %H:%M:%S") if alert.end_time else "Unknown"}</p>
        <p><span class="label">Duration:</span> {self._format_duration(alert.end_time - alert.start_time) if alert.end_time else "Unknown"}</p>
        
        {f"<p>{alert.description}</p>" if alert.description else ""}
        
        <h3>Labels:</h3>
        <pre>{json.dumps(alert.labels, indent=2)}</pre>
        
        <h3>Annotations:</h3>
        <pre>{json.dumps(alert.annotations, indent=2)}</pre>
    </div>
</body>
</html>
"""
        # Attach parts
        part1 = MIMEText(text_content, "plain")
        part2 = MIMEText(html_content, "html")
        msg.attach(part1)
        msg.attach(part2)

        # Send email
        use_ssl = config.get("use_ssl", False)
        smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP

        with smtp_class(config["smtp_server"], config["smtp_port"]) as server:
            if not use_ssl and config.get("use_tls", False):
                server.starttls()

            if "username" in config and "password" in config:
                server.login(config["username"], config["password"])

            server.send_message(msg)

    async def _send_slack_notification(self, channel: NotificationChannel, alert: AlertInstance):
        """
        Send a Slack notification.

        Args:
            channel: Slack channel
            alert: Alert instance
        """
        config = channel.config
        if "webhook_url" not in config:
            logger.error(f"Missing webhook URL for Slack channel {channel.name}")
            return

        # Create payload
        color = {"critical": "#FF0000", "warning": "#FFA500", "info": "#0000FF"}.get(
            alert.severity, "#808080"
        )

        payload = {
            "attachments": [,
                {
                    "fallback": f"[{alert.severity.upper()}] {alert.name}",
                    "color": color,
                    "title": f"[{alert.severity.upper()}] {alert.name}",
                    "text": alert.description or "",
                    "fields": [,
                        {"title": "Status", "value": alert.status, "short": True},
                        {
                            "title": "Time",
                            "value": datetime.fromtimestamp(alert.start_time).strftime(,
                                "%Y-%m-%d %H:%M:%S"
                            ),
                            "short": True,
                        },
                        {
                            "title": "Value",
                            "value": f"{alert.value} {alert.comparison} {alert.threshold}",
                            "short": True,
                        },
                    ],
                    "footer": "MCP Alerting",
                    "ts": int(alert.start_time),
                }
            ]
        }

        # Add labels and annotations
        if alert.labels:
            labels_field = {
                "title": "Labels",
                "value": "\n".join([f"{k}: {v}" for k, v in alert.labels.items()]),
                "short": False,
            }
            payload["attachments"][0]["fields"].append(labels_field)

        if alert.annotations:
            annotations_field = {
                "title": "Annotations",
                "value": "\n".join([f"{k}: {v}" for k, v in alert.annotations.items()]),
                "short": False,
            }
            payload["attachments"][0]["fields"].append(annotations_field)

        # Send to Slack
        webhook_url = config["webhook_url"]

        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Error sending Slack notification: {error_text}")

    async def _send_slack_resolution(self, channel: NotificationChannel, alert: AlertInstance):
        """
        Send a Slack resolution notification.

        Args:
            channel: Slack channel
            alert: Alert instance
        """
        config = channel.config
        if "webhook_url" not in config:
            logger.error(f"Missing webhook URL for Slack channel {channel.name}")
            return

        # Create payload
        duration = (
            self._format_duration(alert.end_time - alert.start_time)
            if alert.end_time
            else "Unknown"
        )

        payload = {
            "attachments": [,
                {
                    "fallback": f"[RESOLVED] {alert.name}",
                    "color": "#36A64F",  # Green for resolved
                    "title": f"[RESOLVED] {alert.name}",
                    "text": alert.description or "",
                    "fields": [,
                        {"title": "Severity", "value": alert.severity, "short": True},
                        {
                            "title": "Started",
                            "value": datetime.fromtimestamp(alert.start_time).strftime(,
                                "%Y-%m-%d %H:%M:%S"
                            ),
                            "short": True,
                        },
                        {
                            "title": "Resolved",
                            "value": (,
                                datetime.fromtimestamp(alert.end_time).strftime("%Y-%m-%d %H:%M:%S")
                                if alert.end_time
                                else "Unknown"
                            ),
                            "short": True,
                        },
                        {"title": "Duration", "value": duration, "short": True},
                    ],
                    "footer": "MCP Alerting",
                    "ts": int(time.time()),
                }
            ]
        }

        # Send to Slack
        webhook_url = config["webhook_url"]

        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Error sending Slack resolution notification: {error_text}")

    async def _send_webhook_notification(self, channel: NotificationChannel, alert: AlertInstance):
        """
        Send a webhook notification.

        Args:
            channel: Webhook channel
            alert: Alert instance
        """
        config = channel.config
        if "url" not in config:
            logger.error(f"Missing URL for webhook channel {channel.name}")
            return

        # Create payload
        payload = {
            "alert": {
                "id": alert.id,
                "name": alert.name,
                "description": alert.description,
                "severity": alert.severity,
                "status": alert.status,
                "value": alert.value,
                "threshold": alert.threshold,
                "comparison": alert.comparison,
                "start_time": alert.start_time,
                "labels": alert.labels,
                "annotations": alert.annotations,
            },
            "timestamp": time.time(),
            "event": "alert",
        }

        # Add custom headers if specified
        headers = config.get("headers", {})

        # Send webhook
        url = config["url"]

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status < 200 or response.status >= 300:
                    error_text = await response.text()
                    logger.error(f"Error sending webhook notification: {error_text}")

    async def _send_webhook_resolution(self, channel: NotificationChannel, alert: AlertInstance):
        """
        Send a webhook resolution notification.

        Args:
            channel: Webhook channel
            alert: Alert instance
        """
        config = channel.config
        if "url" not in config:
            logger.error(f"Missing URL for webhook channel {channel.name}")
            return

        # Create payload
        payload = {
            "alert": {
                "id": alert.id,
                "name": alert.name,
                "description": alert.description,
                "severity": alert.severity,
                "status": alert.status,
                "value": alert.value,
                "threshold": alert.threshold,
                "comparison": alert.comparison,
                "start_time": alert.start_time,
                "end_time": alert.end_time,
                "duration": alert.end_time - alert.start_time if alert.end_time else None,
                "labels": alert.labels,
                "annotations": alert.annotations,
            },
            "timestamp": time.time(),
            "event": "resolution",
        }

        # Add custom headers if specified
        headers = config.get("headers", {})

        # Send webhook
        url = config["url"]

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status < 200 or response.status >= 300:
                    error_text = await response.text()
                    logger.error(f"Error sending webhook resolution: {error_text}")

    def _send_console_notification(self, alert: AlertInstance):
        """
        Send a console notification.

        Args:
            alert: Alert instance
        """
        severity_colors = {
            "critical": "\033[91m",  # Red
            "warning": "\033[93m",  # Yellow
            "info": "\033[94m",  # Blue
        }
        reset = "\033[0m"

        color = severity_colors.get(alert.severity, "")

        # Format notification
        notification = f"""
{color}[ALERT: {alert.severity.upper()}]{reset} {alert.name}
Status: {alert.status}
Time: {datetime.fromtimestamp(alert.start_time).strftime("%Y-%m-%d %H:%M:%S")}
Value: {alert.value} {alert.comparison} {alert.threshold}

{alert.description or ""}

Labels: {json.dumps(alert.labels)}
Annotations: {json.dumps(alert.annotations)}
"""
        logger.warning(notification)

    def _send_console_resolution(self, alert: AlertInstance):
        """
        Send a console resolution notification.

        Args:
            alert: Alert instance
        """
        # Format notification
        duration = (
            self._format_duration(alert.end_time - alert.start_time)
            if alert.end_time
            else "Unknown"
        )

        notification = f"""
\033[92m[RESOLVED]\033[0m {alert.name}
Severity: {alert.severity}
Started: {datetime.fromtimestamp(alert.start_time).strftime("%Y-%m-%d %H:%M:%S")}
Resolved: {datetime.fromtimestamp(alert.end_time).strftime("%Y-%m-%d %H:%M:%S") if alert.end_time else "Unknown"}
Duration: {duration}

{alert.description or ""}

Labels: {json.dumps(alert.labels)}
Annotations: {json.dumps(alert.annotations)}
"""
        logger.info(notification)

    def _format_duration(self, seconds: float) -> str:
        """
        Format a duration in seconds to a human-readable string.

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted duration string
        """
        if seconds < 60:
            return f"{seconds:.1f} seconds"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f} minutes"
        elif seconds < 86400:
            hours = seconds / 3600
            return f"{hours:.1f} hours"
        else:
            days = seconds / 86400
            return f"{days:.1f} days"

    async def create_rule(self, rule: AlertRule) -> bool:
        """
        Create a new alert rule.

        Args:
            rule: Alert rule

        Returns:
            True if successful
        """
        self.rules[rule.id] = rule
        await self.save_rules()
        return True

    async def update_rule(self, rule_id: str, rule: AlertRule) -> bool:
        """
        Update an existing alert rule.

        Args:
            rule_id: Rule ID
            rule: Updated rule

        Returns:
            True if successful
        """
        if rule_id != rule.id:
            # ID changed, remove old rule
            if rule_id in self.rules:
                del self.rules[rule_id]

        self.rules[rule.id] = rule
        await self.save_rules()
        return True

    async def delete_rule(self, rule_id: str) -> bool:
        """
        Delete an alert rule.

        Args:
            rule_id: Rule ID

        Returns:
            True if successful
        """
        if rule_id in self.rules:
            del self.rules[rule_id]
            await self.save_rules()
            return True
        return False

    async def get_rule(self, rule_id: str) -> Optional[AlertRule]:
        """
        Get an alert rule.

        Args:
            rule_id: Rule ID

        Returns:
            Alert rule or None if not found
        """
        return self.rules.get(rule_id)

    async def get_rules(self) -> List[AlertRule]:
        """
        Get all alert rules.

        Returns:
            List of alert rules
        """
        return list(self.rules.values())

    async def silence_rule(self, rule_id: str, duration_minutes: int) -> bool:
        """
        Silence an alert rule for a period of time.

        Args:
            rule_id: Rule ID
            duration_minutes: Duration in minutes

        Returns:
            True if successful
        """
        rule = self.rules.get(rule_id)
        if not rule:
            return False

        # Set silenced until timestamp
        rule.silenced_until = time.time() + (duration_minutes * 60)

        # Resolve any current alerts for this rule
        await self._resolve_alerts(rule_id)

        await self.save_rules()
        return True

    async def unsilence_rule(self, rule_id: str) -> bool:
        """
        Unsilence an alert rule.

        Args:
            rule_id: Rule ID

        Returns:
            True if successful
        """
        rule = self.rules.get(rule_id)
        if not rule:
            return False

        # Clear silenced until timestamp
        rule.silenced_until = None

        await self.save_rules()
        return True

    async def create_channel(self, channel: NotificationChannel) -> bool:
        """
        Create a new notification channel.

        Args:
            channel: Notification channel

        Returns:
            True if successful
        """
        self.channels[channel.id] = channel
        await self.save_channels()
        return True

    async def update_channel(self, channel_id: str, channel: NotificationChannel) -> bool:
        """
        Update an existing notification channel.

        Args:
            channel_id: Channel ID
            channel: Updated channel

        Returns:
            True if successful
        """
        if channel_id != channel.id:
            # ID changed, remove old channel
            if channel_id in self.channels:
                del self.channels[channel_id]

        self.channels[channel.id] = channel
        await self.save_channels()
        return True

    async def delete_channel(self, channel_id: str) -> bool:
        """
        Delete a notification channel.

        Args:
            channel_id: Channel ID

        Returns:
            True if successful
        """
        if channel_id in self.channels:
            del self.channels[channel_id]
            await self.save_channels()
            return True
        return False

    async def get_channel(self, channel_id: str) -> Optional[NotificationChannel]:
        """
        Get a notification channel.

        Args:
            channel_id: Channel ID

        Returns:
            Notification channel or None if not found
        """
        return self.channels.get(channel_id)

    async def get_channels(self) -> List[NotificationChannel]:
        """
        Get all notification channels.

        Returns:
            List of notification channels
        """
        return list(self.channels.values())

    async def get_alerts(self, status: Optional[str] = None) -> List[AlertInstance]:
        """
        Get all alerts, optionally filtered by status.

        Args:
            status: Optional status filter

        Returns:
            List of alerts
        """
        if status:
            return [a for a in self.alerts.values() if a.status == status]
        else:
            return list(self.alerts.values())

    async def get_alert(self, alert_id: str) -> Optional[AlertInstance]:
        """
        Get an alert by ID.

        Args:
            alert_id: Alert ID

        Returns:
            Alert or None if not found
        """
        return self.alerts.get(alert_id)

    async def silence_alert(self, alert_id: str) -> bool:
        """
        Silence a specific alert.

        Args:
            alert_id: Alert ID

        Returns:
            True if successful
        """
        alert = self.alerts.get(alert_id)
        if not alert:
            return False

        alert.status = "silenced"
        await self.save_alerts()
        return True

    async def unsilence_alert(self, alert_id: str) -> bool:
        """
        Unsilence a specific alert.

        Args:
            alert_id: Alert ID

        Returns:
            True if successful
        """
        alert = self.alerts.get(alert_id)
        if not alert and alert.status == "silenced":
            return False

        alert.status = "firing"
        await self.save_alerts()
        return True

    async def resolve_alert(self, alert_id: str) -> bool:
        """
        Manually resolve an alert.

        Args:
            alert_id: Alert ID

        Returns:
            True if successful
        """
        alert = self.alerts.get(alert_id)
        if not alert or alert.status != "firing":
            return False

        alert.status = "resolved"
        alert.end_time = time.time()

        # Send resolution notifications
        await self._send_resolution_notifications(alert)

        await self.save_alerts()
        return True

    async def test_channel(self, channel: NotificationChannel) -> bool:
        """
        Send a test notification to a channel.

        Args:
            channel: Notification channel

        Returns:
            True if successful
        """
        # Create a test alert
        test_alert = AlertInstance(
            id="test_alert",
            rule_id="test_rule",
            name="Test Alert",
            description="This is a test alert to verify notification channel configuration.",
            query="vector(1)",
            value=1.0,
            threshold=0.0,
            comparison="gt",
            severity="info",
            labels={"test": "true"},
            annotations={"test": "true"},
            start_time=time.time(),
            status="firing",
        )

        try:
            await self._send_notification(channel, test_alert)
            return True
        except Exception as e:
            logger.error(f"Error sending test notification: {e}")
            return False
